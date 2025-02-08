import os

class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'mysql+pymysql://root:root@localhost/ocr'
    SQLALCHEMY_TRACK_MODIFICATIONS = False