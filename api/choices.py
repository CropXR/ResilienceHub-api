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