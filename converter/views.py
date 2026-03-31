import os
import tempfile
import zipfile

from django.http import HttpResponse, JsonResponse
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser

from .services import FirebirdMigrationGenerator


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def upload_excel(request):
    arquivo = request.FILES.get('file')

    if not arquivo:
        return JsonResponse({'error': 'Nenhum arquivo enviado.'}, status=400)

    nome = arquivo.name.lower()
    extensoes_permitidas = ('.zip', '.csv', '.xlsx', '.xls')

    if not nome.endswith(extensoes_permitidas):
        return JsonResponse(
            {'error': 'Envie um arquivo válido: .zip, .csv, .xlsx ou .xls'},
            status=400
        )

    temp_input_path = None
    schema_file = None
    data_file = None
    output_zip_path = None

    try:
        # salva o arquivo recebido temporariamente
        sufixo = os.path.splitext(arquivo.name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=sufixo) as temp_file:
            for chunk in arquivo.chunks():
                temp_file.write(chunk)
            temp_input_path = temp_file.name

        # chama o service OOP
        generator = FirebirdMigrationGenerator()
        schema_file, data_file = generator.generate(temp_input_path)

        # empacota os dois arquivos SQL em um zip
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_zip:
            output_zip_path = temp_zip.name

        with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_out:
            zip_out.write(schema_file, arcname=os.path.basename(schema_file))
            zip_out.write(data_file, arcname=os.path.basename(data_file))

        with open(output_zip_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/zip')
            response['Content-Disposition'] = 'attachment; filename="sql_gerado.zip"'
            return response

    except Exception as e:
        return JsonResponse(
            {'error': f'Erro ao processar arquivo: {str(e)}'},
            status=500
        )

    finally:
        for path in [temp_input_path, schema_file, data_file, output_zip_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass