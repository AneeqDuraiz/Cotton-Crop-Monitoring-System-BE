from django.urls import path
from .views import BareSoilDetectionView, ClassificationView, CropRotationView, ClassificationView,GetPointsNDVIView, CropRotationView, DeletePatchJobsView, FarmView, FieldView,GetStoredAvgNDVIView, GetFields,FarmDetail, AvgNDVI, GetJobsView , GridNDVI, SeasonView,PatchFieldView,JobView, SeasonDetail,DeleteFieldView,GetSeasons, FieldStatsView, SoilEstimationView


urlpatterns = [
    
    path('farm/', FarmView.as_view() ),
    path('farm/<int:id>/', FarmDetail.as_view()),
    
    path('field/', FieldView.as_view() ),
    path('field/putStats/<int:fieldId>/', FieldStatsView.as_view() ),
    path('field/<int:farmid>/<int:seasonid>/', GetFields.as_view()),
    path('field/deleteField/<int:fieldId>/<int:seasonId>/', DeleteFieldView.as_view()),
    path('field/patchField/<int:fieldId>/<int:seasonId>/', PatchFieldView.as_view()),
    path('field/getAvgNdvi/<int:fieldID>/<int:seasonID>/', GetStoredAvgNDVIView.as_view()),

    path('field/getPointsNdvi/', GetPointsNDVIView.as_view()),

    path('field/avgndvi/<int:id>/', AvgNDVI.as_view()),
    path('field/gridndvi/', GridNDVI.as_view()), 

    path('season/', SeasonView.as_view()),
    path('season/<int:id>/', SeasonDetail.as_view()),
    path('season/getSeason/<int:farmId>/', GetSeasons.as_view()),

    path('job/', JobView.as_view()),
    path('job/getjobs/<int:seasonId>/', GetJobsView.as_view()),
    path('job/deletejob/<int:jobId>/', DeletePatchJobsView.as_view()),
    path('job/patchjob/<int:jobId>/', DeletePatchJobsView.as_view()),

    path('field/getPrediction/', ClassificationView.as_view()),
     path('field/getBareSoilPrediction/', BareSoilDetectionView.as_view()),
    path('field/getSOMPrediction/', SoilEstimationView.as_view()),


    path('farm/getCropRotation/<int:farmId>/', CropRotationView.as_view()),
    


]