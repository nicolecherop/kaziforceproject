from django.apps import AppConfig
from django.db.models.signals import post_save, post_delete


class RecruitmentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'recruitment'

    def ready(self):
        from .models import Skill, Occupation
        from .matching import clear_taxonomy_cache
        for model in (Skill, Occupation):
            post_save.connect(clear_taxonomy_cache, sender=model, weak=False,
                              dispatch_uid=f'kaziforce-{model.__name__}-taxonomy-save')
            post_delete.connect(clear_taxonomy_cache, sender=model, weak=False,
                                dispatch_uid=f'kaziforce-{model.__name__}-taxonomy-delete')
