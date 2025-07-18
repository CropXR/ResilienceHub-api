#isa_api/choices.py
from django.db import models

class SecurityLevel(models.TextChoices):
    PUBLIC = 'public', 'Public'
    INTERNAL = 'internal', 'Internal'
    RESTRICTED = 'restricted', 'Restricted'
    CONFIDENTIAL = 'confidential', 'Confidential'
    
class MeasurementType(models.TextChoices):
    GENOMICS = 'genomics', 'Genomics'
    TRANSCRIPTOMICS = 'transcriptomics', 'Transcriptomics'
    PROTEOMICS = 'proteomics', 'Proteomics'
    METABOLOMICS = 'metabolomics', 'Metabolomics'
    PHENOTYPING = 'phenotyping', 'Phenotyping'
    OTHER = 'other', 'Other'

class TechnologyPlatform(models.TextChoices):
    SEQUENCING = 'seq', 'Sequencing'
    MICROARRAY = 'micro', 'Microarray'
    MASS_SPECTROMETRY = 'ms', 'Mass Spectrometry'
    NMR = 'nmr', 'NMR'
    OTHER = 'other', 'Other'
    
class WorkPackageChoices(models.TextChoices):
    WPC1 = 'WPC1', 'WPC1'
    WPC2 = 'WPC2', 'WPC2'
    WPC3 = 'WPC3', 'WPC3'
    WPC4 = 'WPC4', 'WPC4'
    WPC5 = 'WPC5', 'WPC5'
    WPC6 = 'WPC6', 'WPC6'
    WPC7 = 'WPC7', 'WPC7'
    WPT = 'WPT', 'WPT'
    WPD = 'WPD', 'WPD'
    S1 = 'S1', 'S1'
    S2 = 'S2', 'S2'
    S3 = 'S3', 'S3'
    S4 = 'S4', 'S4'
    S5 = 'S5', 'S5'
    S6 = 'S6', 'S6'