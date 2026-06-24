from flask import Flask, render_template, request
from CW14model import InputForm
from calcport import charge_et_sections

app = Flask(__name__)



@app.route('/', methods=['GET', 'POST'])

def index():
    form = InputForm(request.form)
    if request.method == 'POST' and form.validate():
        geom = {"hpot":form.hpot.data*100,
                "portee":form.portee.data*100,
                "pente":form.pente.data/100,
                "longueur":form.longueur.data*100,
                "entraxe":form.entraxe.data*100,
                "h_acro":form.h_acro.data*100}
        locali = {"nom_commune": form.commune.data,
                  "ancien_nom_comm": form.commune.data,
                  "departement": form.departement.data,
                  "altitude": form.altitude.data,
                  "rugosite":form.rugo.data}
        chpro = {"couv" :form.cp_couv.data,
                 "divers" : form.cp_div.data}
        result = charge_et_sections(geom, locali, chpro)
        
    else:
        result = None

    return render_template("CW14view.html", form=form, result=result)

if __name__ == '__main__':
    app.run(debug=True)


