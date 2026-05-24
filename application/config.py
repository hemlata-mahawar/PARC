from dotenv import load_dotenv
import os

load_dotenv()

class Config():
    DEBUG = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class LocalDevelopmentConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI')
    DEBUG = True
    SECRET_KEY = os.getenv('SECRET_KEY')
    SECURITY_PASSWORD_HASH = os.getenv('SECURITY_PASSWORD_HASH')
    SECURITY_PASSWORD_SALT = os.getenv('SECURITY_PASSWORD_SALT')
    SECURITY_TOKEN_AUTHENTICATION_HEADER = 'Authentication-Token'
    WTF_CSRF_ENABLED = False


class cacheConfig():
    CACHE_TYPE = "RedisCache"
    # CACHE_REDIS_URL = "redis://localhost:6379/2"
    CACHE_REDIS_URL = os.getenv("REDIS_URL")
    CACHE_DEFAULT_TIMEOUT = 500 
    CACHE_KEY_PREFIX = "mycache"