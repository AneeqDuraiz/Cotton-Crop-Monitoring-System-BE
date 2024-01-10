from django.contrib import admin
from api.models import Farm, Field, Season
# Register your models here.



@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    list_display = ['name', 'user']
    


# @admin.register(Field)
# class FieldAdmin(admin.ModelAdmin):
#     list_display = ['name', 'farm','season', 'coordinates']
#    # list_editable = ['coordinates']

# @admin.register(Season)
# class FieldAdmin(admin.ModelAdmin):
#     list_display = ['name', 'start_date','end_date']
