from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('importer', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='question',
            name='question_bank',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]