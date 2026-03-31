# Excel / CSV / ZIP to SQL Converter

Sistema full stack para conversão de arquivos `.csv`, `.xlsx`, `.xls` e `.zip` em scripts SQL, com frontend em React e backend em Django.

## Visão geral

O sistema permite que o usuário envie um arquivo de dados e receba como resultado scripts SQL gerados automaticamente.

Atualmente o projeto possui:

- upload de arquivos `.zip`, `.csv`, `.xlsx` e `.xls`
- preview do SQL gerado
- download do resultado em `.zip`
- interface web com drag and drop
- backend preparado para processar arquivos e converter para SQL

---

## Tecnologias utilizadas

### Frontend
- React
- Vite
- Axios
- CSS puro

### Backend
- Python
- Django
- Django REST Framework
- Pandas
- NumPy
- OpenPyXL

---

## Estrutura do projeto

```txt
project/
├─── converter/
│      ├── services.py
│      ├── views.py
│      ├── urls.py
│      └── ...
│─── core/
│      ├── settings.py
│      ├── urls.py
│      └── ...
│── manage.py
│
└── frontend/
    ├── src/
    │   ├── components/
    │   │   └── UploadForm.jsx
    │   ├── App.jsx
    │   └── index.css
    ├── package.json
    └── ...

```
## Funcionalidade

- ``pip install requirements.txt``
- Preencher `.envmodel` e renomear para `.env`
- Rodar django migrate na pasta raiz e `python manage.py runserver` para a api funcionar
- Entrar na pasta com `cd frontend` e rodar o `npm run dev` para o site

## Futuras implementações

- Suporte a múltiplas abas do excel
- Escolha do banco de destino
- Deploy em produção
- Log de conversões