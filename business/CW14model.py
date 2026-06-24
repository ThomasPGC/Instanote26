from wtforms import Form, FloatField, StringField, validators, SelectField, FormField, HiddenField 


# from flask_wtf import FlaskForm


class GeomForm(Form):
    hpot = FloatField(
        label='Hauteur poteau (m)',
        validators=[validators.InputRequired(), validators.NumberRange(min=1, max=20)])
    portee = FloatField(
        label='Portée (m)',
        validators=[validators.InputRequired(), validators.NumberRange(min=1, max=50)])
    pente = FloatField(
        label='Pente couverture en %',
        validators=[validators.InputRequired(), validators.NumberRange(min=3, max=200)])
    longueur = FloatField(
        label='Longueur totale bâtiment (m)',
        validators=[validators.InputRequired(), validators.NumberRange(min=1, max=200)])
    entraxe = FloatField(
        label='Entraxe portiques (m)',
        validators=[validators.InputRequired(), validators.NumberRange(min=1, max=20)])
    h_acro = FloatField(
        label='Hauteur acrotère / tête poteau (m)',
        validators=[validators.InputRequired(), validators.NumberRange(min=0, max=10)])


class GeomFormNonID(Form):
    hpot = FloatField(
        label='Hauteur poteau (m)',
        validators=[validators.InputRequired(), validators.NumberRange(min=1, max=20)])
    portee = FloatField(
        label='Portée (m)',
        validators=[validators.InputRequired(), validators.NumberRange(min=1, max=4)],
        description='Valeur limitée à 4 m dans cette version de démonstration')
    pente = FloatField(
        label='Pente couverture en %',
        validators=[validators.InputRequired(), validators.NumberRange(min=3, max=200)])
    longueur = FloatField(
        label='Longueur totale bâtiment (m)',
        validators=[validators.InputRequired(), validators.NumberRange(min=1, max=200)])
    entraxe = FloatField(
        label='Entraxe portiques (m)',
        validators=[validators.InputRequired(), validators.NumberRange(min=1, max=20)])
    h_acro = FloatField(
        label='Hauteur acrotère / tête poteau (m)',
        validators=[validators.InputRequired(), validators.NumberRange(min=0, max=10)])


class ChargeForm(Form):
    couv = FloatField(
        label='Poids propre couverture (kg/m²)',
        validators=[validators.InputRequired(), validators.NumberRange(min=1, max=200)],
        description='Le poids des pannes est ajouté automatiquement')
    divers = FloatField(
        label='Poids propre divers sous toiture (kg/m²)',
        validators=[validators.NumberRange(min=0, max=200)],
        description='Par exemple: éclairage, isolation, panneaux solaires')


class LocalForm(Form):
    adresse = StringField(
        label='Lieu de construction',
        validators=[validators.InputRequired()],
        description="Tapez ici l'adresse de construction, ex: 1 place de la Comédie Montpellier")
    adresse_reco = StringField(
        label='Adresse reconnue',
        # default='1 place de la Comédie Montpellier',
        validators=[validators.InputRequired()],
        description="Ce champ doit se remplir automatiquement")

    nom_commune = StringField(
        label='Commune',
        validators=[validators.InputRequired()],
        description="Ce champ doit se remplir automatiquement")

    ancien_nom_comm = StringField(
        label='Ancienne commune',
        # default='Montpellier',
        # validators=[validators.InputRequired()],
        description="Ce champ doit se remplir automatiquement, si nécessaire")

    departement = StringField(
        label='Département',
        validators=[validators.InputRequired()],
        description="Ce champ doit se remplir automatiquement")

    longi = HiddenField() # Champ caché pour la longitude
    lati = HiddenField()  # Champ caché pour la latitude

    altitude = FloatField(
        label='Altitude', # Gardez celui-ci visible
        validators=[validators.InputRequired(), validators.NumberRange(min=0, max=2000)],
        description="Ce champ doit se remplir automatiquement")

    rugosite = SelectField(
        label='Rugosité terrain environnant',
        choices=[('0', "0 - mer, plan d'eau de 5 km ou plus"),
                 ('II', 'II - rase campagne avec ou non obstacles isolés'),
                 ('IIIa', 'IIIa - bocage, vigne, campagne avec haies'),
                 ('IIIb', 'IIIb - bocage dense, verger, zone urbanisée ou industrielle'),
                 ('IV', 'IV - ville dont 15% de la surface a des constructions de hauteur moyenne 15 m , forêt')],
        # default="IIIa",
        validators=[validators.InputRequired()],
        description="Choisissez le type de terrain environnant la construction")


class InputForm(Form):
    geom = FormField(GeomForm, label="Géométrie")
    charges = FormField(ChargeForm, label="Charges")
    local = FormField(LocalForm, label="Localisation")


class InputFormNonID(Form):
    geom = FormField(GeomFormNonID, label="Géométrie")
    charges = FormField(ChargeForm, label="Charges")
    local = FormField(LocalForm, label="Localisation")
