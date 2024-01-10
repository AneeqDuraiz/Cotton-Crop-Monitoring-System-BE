from django.db import models
from users.models import User

# Create your models here.
class Farm(models.Model):
    name = models.CharField(max_length=255)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

class Season(models.Model):
    name = models.CharField(max_length=255)
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()

class Field(models.Model):
    name = models.CharField(max_length=255)
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE)

class Field_Data(models.Model):
    field = models.ForeignKey(Field, on_delete=models.CASCADE)
    season = models.ForeignKey(Season, on_delete=models.CASCADE)
    coordinates = models.TextField()
    crop_name = models.CharField(max_length=200, null=True, blank=True)
    avg_ndvi = models.FloatField()
    area = models.FloatField()
    created_at = models.DateField(auto_now_add=True)

class Field_Grid(models.Model):
    field_data = models.ForeignKey(Field_Data, on_delete=models.CASCADE)
    lat_lng = models.TextField()
    ndvi = models.FloatField()


class Job(models.Model):
    season = models.ForeignKey(Season, on_delete=models.CASCADE)
    type = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    created_at = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    due_time = models.TimeField()
    status = models.CharField(max_length=100)
    

class Job_Input(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    unit = models.CharField(max_length=100)
    type = models.CharField(max_length=100)
    application_rate_per_hector = models.FloatField()
    total = models.FloatField()
    n1 = models.FloatField()
    n2 = models.FloatField()
    n3 = models.FloatField()
    n4 = models.FloatField()
    n5 = models.FloatField()
    n6 = models.FloatField()

class Job_Field(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    field = models.ForeignKey(Field, on_delete=models.CASCADE)

