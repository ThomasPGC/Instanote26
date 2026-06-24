#!/usr/bin/python3
#coding: utf-8

"""Module pour trouver les caractéristiques de profils dans un tableau."""

import csv
import os

module_dir = os.path.abspath(os.path.dirname(__file__))

"""Renvoie un tuple de tous les IPE."""


class Tuple_tous_ipe:
    def __init__(self):

        self.donnees = tuple()
        with open(os.path.join(module_dir, "./IPE.csv")) as profiles:
            read_csv = csv.DictReader(profiles, delimiter=',')
            for ligne in read_csv:
                proftuple = {}
                for  cle, val in ligne.items():
                    try:
                        val = float(val.replace(",","."))
                    except:
                        pass
                    proftuple[cle] = val
                self.donnees +=(proftuple,)



    def trouve_val(self,prof, car):
        """Trouve une valeur de caractéristique à partir du nom de profil et de la caractéristique."""
        for section in self.donnees:
            if section["Nom"] == prof:
                return section[car]

    def trouve_premier(self, car, val):
        """Trouve le nom du premier profil ayant la caractéristique supérieure ou égale à celle passée en argument."""
        for section in self.donnees:
            try:
                if section[car] >= val:
                    return section["Nom"]
            except:
                return "valeur hors plage"

    def trouve_decal(self,prof,dec):
        """Trouve le nom de la section decalée à partir du nom de profil et de la valeur de décalage."""
        for index, section in enumerate(self.donnees):
            if section["Nom"] == prof:
                if index+dec < 0:
                    return "IPE 80"
                else:
                    try:
                        return self.donnees[index+dec]["Nom"]
                    except:
                        return "IPE 600"


    def dict_carac(self, num):
        """Renvoie un dictionnaire des caractéristiques à partir du nom de profil."""

        for row in self.donnees:
            if row["Nom"] == num:
                return row


if __name__ == "__main__":

    IPE = Tuple_tous_ipe()

    print("Wel de l'IPE 300 = ",IPE.trouve_val("IPE 300","Wel.y"))

    print("Profil plus petit que l'IPE 80 : ",IPE.trouve_decal("IPE 80",-1)["Nom"])

    print("Ensemble des caractéristiques de l'IPE 220 : ",IPE.dict_carac("IPE 220"))
    print("Caractéritiques de ffoo220 : ",IPE.dict_carac("ffoo220"))

    print("Caractéristiques d'un IPE dont la hauteur mini est 200 mm : ",IPE.trouve_premier("h",200))
    print("Caractéristiques d'un IPE dont la hauteur mini est 800 mm : ",IPE.trouve_premier("h",800))
