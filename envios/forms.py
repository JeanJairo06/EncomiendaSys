from django import forms
from .models import Encomienda


class EncomiendaForm(forms.ModelForm):

    class Meta:
        model = Encomienda

        fields = '__all__'