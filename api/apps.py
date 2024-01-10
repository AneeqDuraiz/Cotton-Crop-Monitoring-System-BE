from django.apps import AppConfig
#from api.views import schedule_next_update

class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    # def ready(self):
    #     from api.views import schedule_next_update
    #     # Run the background task on app startup
    #     print("sssss")
    #     schedule_next_update()