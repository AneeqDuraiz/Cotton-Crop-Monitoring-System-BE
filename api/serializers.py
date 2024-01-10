from rest_framework import serializers
from .models import Farm, Field, Season,Field_Data, Field_Grid, Job, Job_Field, Job_Input


class FarmSerializer(serializers.ModelSerializer):
    class Meta:
        model = Farm
        fields = ['id', 'name', 'user']

class SeasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Season
        fields = ['id','farm', 'name' , 'start_date', 'end_date']

class FieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = Field
        fields = ['id', 'name' , 'farm']

class FieldDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = Field_Data
        fields = ['id' , 'coordinates','season', 'crop_name', 'field', 'avg_ndvi', 'area', 'created_at']


class FieldGridSerializer(serializers.ModelSerializer):
    class Meta:
        model = Field_Grid
        fields = ['id', 'field_data' , 'lat_lng', 'ndvi']


class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = ['id', 'season' , 'type', 'name','created_at', 'due_date', 'due_time', 'status']

class JobInputSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job_Input
        fields = ['id', 'job','name' ,'type', 'unit', 'application_rate_per_hector','total', 'n1', 'n2', 'n3', 'n4', 'n5', 'n6']

class JobFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job_Field
        fields = [ 'job', 'field']