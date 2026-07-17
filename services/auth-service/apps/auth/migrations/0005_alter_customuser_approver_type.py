# Generated for FlowDesk auth approver_type null cleanup.

from django.db import migrations, models


def fill_blank_approver_type(apps, schema_editor):
    CustomUser = apps.get_model("flowauth", "CustomUser")
    CustomUser.objects.filter(approver_type__isnull=True).update(approver_type="")


class Migration(migrations.Migration):

    dependencies = [
        ("flowauth", "0004_customuser_signature_image_customuser_stamp_image"),
    ]

    operations = [
        migrations.RunPython(fill_blank_approver_type, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="customuser",
            name="approver_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("registrar", "Registrar"),
                    ("dean", "Dean"),
                    ("hod", "Head of Department"),
                    ("admin_assistant", "Administrative Assistant"),
                    ("faculty_council", "Faculty Scientific Council"),
                    ("dvc", "Deputy Vice Chancellor"),
                    ("supervisor", "Supervisor"),
                ],
                db_index=True,
                max_length=30,
            ),
        ),
    ]
