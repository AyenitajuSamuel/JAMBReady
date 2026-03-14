from django.apps import AppConfig
 
 
class UsersConfig(AppConfig):
    name = "users"
 
    def ready(self):
        pass  # Signal handlers will be imported here in future...