import os
from dotenv import load_dotenv
load_dotenv('/home/apps/web-a-inefablestore/.env')
print('CATALOG_PATH:', os.environ.get('REVENDEDORES_CATALOG_PATH'))
print('CONNECTION_API_URL:', os.environ.get('CONNECTION_API_URL'))
