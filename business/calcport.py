#! /usr/bin/python3
# coding: utf-8

"""Calcul d'un portique selon la méthode des déplacements.

écrit par Thomas PG Clause - tous droits réservés

portique plan exemple polycopié calcul structures 2 juin 96 ENSAM chapitre 4_6

unités utilisées: cm et daN

repère global: axe X horizontal, croissant de la gauche vers la droite
                axe Y vertical, croissant vers le haut

 axes locaux: axe X du noeud de plus petit numéro vers le plus grand
               axe Y perpendiculaire direct à X (90° sens trigo)

 = système d'axe A du polycop
"""

from math import sqrt, atan, pi, cos, sin
import time
import logging
import pprint 
import pathlib
import numpy as np
from lecture_ipe_csv import Tuple_tous_ipe
import chargement_nv as chnv

E = 2100000  # daN/cm²
IPE = Tuple_tous_ipe()
# print("Premier IPE de la liste : ", IPE.donnees[0]["Nom"])


GEOMTEST = {"hpot": 400, "portee": 1600, "pente": 0.25, "longueur": 2400,
            "entraxe": 600, "h_acro": 0}

LOCALITEST = {"nom_commune": "Ganges",
              "ancien_nom_comm": "chaine",
              "departement": "34",
              "altitude": 120,
              "rugosite": "chaine"}

CPTEST = {"couv": 20, "divers": 3}

CHARGETEST = [("CP_", [-1.2, -1.2, -1.2, -1.2, -1.2, -1.2],
               [0, 0, 0, 0, 0, 0,
                0, 0, 0, 0, -1000, 0,
                0, 0, 0, 0, 0, 0,
                0, 0, 0]),
              ("NEI_", [0, -2.1, -2.1, -2.1, -2.1, 0],
               [0, 0, 0, 0, 0, 0,
                0, 0, 0, 0, 0, 0,
                0, 0, 0, 0, 0, 0,
                0, 0, 0]),
              ("NEI_ACCI", [0, -4.2, -4.2, -4.2, -4.2, 0],
               [0, 0, 0, 0, 0, 0,
                0, 0, 0, 0, 0, 0,
                0, 0, 0, 0, 0, 0,
                0, 0, 0]),
              ("VENT_G_DI", [-2.4, .6, .6, .6, .6, .6],
               [0, 0, 0, 500, 0, 0,
                0, 0, 0, 0, 0, 0,
                0, 0, 0, 500, 0, 0,
                0, 0, 0]),
              ("VENT_D_SI", [2.4, 2.4, 2.4, 2.4, 2.4, -.6],
               [0, 0, 0, -500, 0, 0,
                0, 0, 0, 0, 500, 0,
                0, 0, 0, -500, 0, 0,
                0, 0, 0])]


def jarret(section, coeff_hauteur=1.66):
    """Calcul jarret."""
    b = IPE.trouve_val(section, "b")
    h = coeff_hauteur * IPE.trouve_val(section, "h")
    tf = IPE.trouve_val(section, "tf")
    tw = IPE.trouve_val(section, "tw")

    I = (2 * b * tf * ((h - .5 * tf) / 2) ** 2 + (tw * (h - 2 * tf) ** 3) / 12) / 10000
    A = (2 * b * tf + tw * (h - 2 * tf)) / 100
    Avz = (h * tw) / 100
    Wpl = 2 * (((h / 2 - tf) ** 2) * tw / 2 + b * tf * (h / 2 - tf / 2)) / 1000
    return {"Iy": I, "A": A, "Avz": Avz, "Wpl.y": Wpl}


def trouve_commun(liste1, liste2):
    for el in liste1:
        if el in liste2:
            return el
    return -1


class Node:
    """Cette classe est celle de noeud (Node en anglais), au sens de l'objet
mathématique dans le cadre de la théorie des poutres"""

    def __init__(self, X, Y, num, type_app="lib"):
        """ un noeud est défini par ses coordonnées et un type, soit appui
articulé, soit appui encastré, soit libre"""
        self.X = X
        self.Y = Y
        self.A = num
        self.T = type_app

    def indexe_barres(self, barres):
        self.barres_orig = []
        self.barres_arriv = []

        for i, barre in enumerate(barres):
            if barre.Ai == self:
                self.barres_orig.append(i)
            if barre.Aj == self:
                self.barres_arriv.append(i)


class Beam:
    """Cette classe est celle de poutre (Beam en anglais), au sens de l'objet
mathématique dans le cadre de la théorie des poutres"""

    def __init__(self, nOr, nExtr, section):
        """ une barre est définie à minima par un noeud d'origine, un noeud
de fin et une section (IPE 200 etc.)"""
        self.Ai = nOr
        self.Aj = nExtr
        self.longueur = sqrt((self.Ai.X - self.Aj.X) ** 2 + (self.Ai.Y - self.Aj.Y) ** 2)
        self.calc_R()
        self.mod_attr_resist(section)

        self.charge = 0  # charge linéaire

        self.Sij = np.zeros([3, 1])
        self.Sji = np.zeros([3, 1])

        self.Fij = np.zeros([3, 1])
        self.Fji = np.zeros([3, 1])

        self.efforts_noeud = []

    def calc_KL_ij(self):
        self.Kij = np.dot(np.dot(self.R.T, self.kij), self.R)
        self.Kji = np.dot(np.dot(self.R.T, self.kji), self.R)
        self.Lij = np.dot(np.dot(self.R.T, self.lij), self.R)
        self.Lji = np.dot(np.dot(self.R.T, self.lji), self.R)

    def calc_R(self):
        self.R = np.eye(3, 3)
        self.R[0, 0] = (self.Aj.X - self.Ai.X) / self.longueur
        self.R[1, 1] = self.R[0, 0]
        self.R[1, 0] = (self.Ai.Y - self.Aj.Y) / self.longueur
        self.R[0, 1] = -self.R[1, 0]

    def calc_kl_ij(self):
        self.kij = np.zeros([3, 3])
        self.kij[0, 0] = E * self.aire / self.longueur
        self.kij[1, 1] = 12 * E * self.I / self.longueur ** 3
        self.kij[2, 1] = 6 * E * self.I / self.longueur ** 2
        self.kij[1, 2] = 6 * E * self.I / self.longueur ** 2
        self.kij[2, 2] = 4 * E * self.I / self.longueur
        self.kji = np.copy(self.kij)
        self.kji[2, 1] = -self.kij[2, 1]
        self.kji[1, 2] = -self.kij[2, 1]
        self.lji = np.copy(self.kij)
        self.lji[0, 0] = -self.kij[0, 0]
        self.lji[1, 1] = -self.kij[1, 1]
        self.lji[1, 2] = -self.kij[1, 2]
        self.lji[2, 2] = 2 * E * self.I / self.longueur
        self.lij = np.copy(self.lji)
        self.lij[1, 2] = -self.lji[1, 2]
        self.lij[2, 1] = -self.lji[2, 1]

    def alpha(self):
        """détermination de l'angle du repère local"""
        if (self.Ai.X - self.Aj.X) == 0:
            angle = pi / 2 * (self.Aj.Y - self.Ai.Y) / abs(self.Aj.Y - self.Ai.Y)
        else:
            angle = atan((self.Ai.Y - self.Aj.Y) / (self.Ai.X - self.Aj.X))
        return angle

    def eff(self):
        """détermination de la matrice des efforts"""
        self.Fij = np.dot(self.R.T, self.Sij)
        self.Fji = np.dot(self.R.T, self.Sji)

    def calcSij_perp(self, charge):
        """détermination de la matrice S sous charges perpendiculaires à la barre"""
        self.Sij = [[0],
                    [-charge * self.longueur / 2],
                    [-charge * (self.longueur) ** 2 / 12]]
        self.Sji = [[0],
                    [-charge * self.longueur / 2],
                    [charge * (self.longueur) ** 2 / 12]]

    def calcSij_vert(self, charge):
        """détermination de la matrice S sous charges verticales"""
        self.Sij = [[-charge * sin(self.alpha()) * self.longueur / 2],
                    [-charge * cos(self.alpha()) * self.longueur / 2],
                    [-charge * cos(self.alpha()) * (self.longueur) ** 2 / 12]]
        self.Sji = [[-charge * sin(self.alpha()) * self.longueur / 2],
                    [-charge * cos(self.alpha()) * self.longueur / 2],
                    [charge * cos(self.alpha()) * (self.longueur) ** 2 / 12]]

    def mod_attr_resist(self, section_dict):
        self.aire = section_dict["A"]
        self.I = section_dict["Iy"]
        self.Wpl = section_dict["Wpl.y"]
        self.Avz = section_dict["Avz"]
        self.calc_kl_ij()
        self.calc_KL_ij()


def calcport(A, B, K, F, cas=CHARGETEST[2], lim_fy=235):
    """fonction principale de calcul des déplacements et des efforts internes

    entrées:
        - GEOMTEST = {"hpot":400, "portee":1600, "pente":0.035}
        - cas = ("CP_", [-1.2, 0, 0, 0, 0, -1.2],
                  [0, 0, 0, 0, 0, 0,
                   0, 0, 0, 0, 0, 0,
                   0, 0, 0])
            la première valeur du cas doit être son nom,
            elle doit contenir soit CP, soit NEI, soit VEN
            la seconde est un tableau de charges par barre
            la troisième est un tableau de charges par noeud,
            ordre  = X,Y,M, en daN
        - sect_ ... explicite

    sortie:
        dictionnaire déplacements et efforts déterminants


        """

    # for barretest in B:
    #     print("longueur = ", barretest.longueur, "; alpha = ", barretest.alpha())
    #     print(barretest.Sij)

    # construction de la matrice colonne des forces

    # F = crea_matrice_force(len(A), B, cas)

    # print("matrice des forces \n", F)

    # F[3, 0] = F[3, 0]-200
    # F[15, 0] = F[15, 0]-200

    # retrait des lignes et colonnes correspondant aux noeuds appuyés
    # ici articulés, supprimmer une ligne de plus pour encastrés
    # et regarder aux bons endroits pour les déplacements!

    K_sans_app = K
    F_sans_app = F

    for i in range(len(A) * 3 - 2, len(A) * 3 - 4, -1):
        K_sans_app = np.delete(K_sans_app, i, axis=0)
        K_sans_app = np.delete(K_sans_app, i, axis=1)
        F_sans_app = np.delete(F_sans_app, i, axis=0)

    for i in range(1, -1, -1):
        K_sans_app = np.delete(K_sans_app, i, axis=0)
        K_sans_app = np.delete(K_sans_app, i, axis=1)
        F_sans_app = np.delete(F_sans_app, i, axis=0)

    # résolution du système d'équations linéaires pour trouver les déplacements des
    # noeuds

    D = np.linalg.solve(K_sans_app, F_sans_app)
    # print("Déplacements \n", D)

    D_avec_app = D
    D_avec_app = np.insert(D_avec_app, 0, 0)
    D_avec_app = np.insert(D_avec_app, 0, 0)
    D_avec_app = np.insert(D_avec_app, len(D_avec_app) - 1, 0)
    D_avec_app = np.insert(D_avec_app, len(D_avec_app) - 1, 0)

    # F_tot = np.add(-F.flatten(), np.dot(K,D_avec_app))

    return calculer_et_verifier_resultats(B, D_avec_app)

    

def calculer_et_verifier_resultats(B, D_avec_app,  fy=235.0):
    """
    Effectue le post-traitement, calcule les efforts et les taux de travail.
    Unités internes de base : daN, cm.
    fy: Limite élastique de l'acier fournie en MPa (N/mm^2). Défaut S235.
    """
     # Limite de cisaillement en MPa (N/mm^2)
    fv = fy / sqrt(3.0)

    # Limites converties en daN/mm^2 pour la comparaison
    fy_limit_daN_mm2 = fy / 10.0
    fv_limit_daN_mm2 = fv / 10.0

    eff_int = []
    for barre in B:
        s_barre = np.concatenate((barre.Sij, barre.Sji))
        k_barre = np.concatenate((np.concatenate((barre.kij, barre.lji)),
                                  np.concatenate((barre.lij, barre.kji))),
                                 axis=1)
        di_barre = np.zeros([3, 1])
        for i in range(3):
            di_barre[i] = D_avec_app[barre.Ai.A * 3 + i]
        dj_barre = np.zeros([3, 1])
        for j in range(3):
            dj_barre[j] = D_avec_app[barre.Aj.A * 3 + j]
        d_rot_barre = np.concatenate((np.dot(barre.R, di_barre), np.dot(barre.R, dj_barre)))
        barre.efforts_noeuds = np.add(-s_barre, np.dot(k_barre, d_rot_barre))
        # print ("barre ", barre.Ai.A, "\n", barre.efforts_noeuds)
        # print("Wpl ",barre.Wpl)
        eff_int.append(barre.efforts_noeuds)

    ens_resu = dict(depl_t_p_g=D_avec_app[3],
                    depl_t_p_d=D_avec_app[15],
                    fleche_fait=D_avec_app[10],
                    tx_mom_pot_g=eff_int[0][5][0] / (B[0].Wpl * fy_limit_daN_mm2)/ 100,
                    tx_mom_renf_g=eff_int[1][2][0] / (B[1].Wpl * fy_limit_daN_mm2)/ 100,
                    tx_mom_pied_arba_g=eff_int[2][2][0] / (B[2].Wpl * fy_limit_daN_mm2)/ 100,
                    tx_mom_fait=eff_int[2][5][0] / (B[2].Wpl * fy_limit_daN_mm2)/ 100,
                    tx_mom_pied_arba_d=eff_int[3][5][0] / (B[3].Wpl * fy_limit_daN_mm2)/ 100,
                    tx_mom_renf_d=eff_int[4][5][0] / (B[4].Wpl * fy_limit_daN_mm2)/ 100,
                    tx_mom_pot_d=eff_int[5][2][0] / (B[5].Wpl * fy_limit_daN_mm2)/ 100,
                    tx_cis_pot_g=eff_int[0][1][0] / (B[0].Avz * fv_limit_daN_mm2)/ 100,
                    tx_cis_renf_g=eff_int[1][1][0] / (B[1].Avz * fv_limit_daN_mm2)/ 100,
                    tx_cis_pied_arba_g=eff_int[2][1][0] / (B[2].Avz * fv_limit_daN_mm2)/ 100,
                    tx_cis_pied_arba_d=eff_int[3][4][0] / (B[3].Avz * fv_limit_daN_mm2)/ 100,
                    tx_cis_renf_d=eff_int[4][4][0] / (B[4].Avz * fv_limit_daN_mm2)/ 100,
                    tx_cis_pot_d=eff_int[5][4][0] / (B[5].Avz * fv_limit_daN_mm2) /100)

    # print(cas[0])
    # for cle, valeur in ens_resu.items():
    # print(cle, round(valeur,2))

    return ens_resu

   


def crea_matrice_force(nb_noeuds, B, cas):
    # on peut calculer les charges gravitaires directement dans le repère global
    # donc faire les Fij sans passer par les Sij
    # les moments sont le produit de la longueur réelle par la charge et par
    # la longueur de bras de levier (en pratique la distance horizontale
    # attention, les signes sont mauvais apparemment (cf fonction de test, * - 1 pour que ça passe)
    if "CP" in cas[0]:
        for i, barre in enumerate(B):
            barre.calcSij_vert(cas[1][i] - barre.aire * 7.85 * 10 ** -3)
            barre.eff()

    if "NEI" in cas[0]:
        for i, barre in enumerate(B):
            barre.calcSij_vert(cas[1][i] * cos(barre.alpha()))
            barre.eff()

    if "VEN" in cas[0]:
        for i, barre in enumerate(B):
            barre.calcSij_perp(cas[1][i])
            barre.eff()

    lignes = []
    for i in range(nb_noeuds):
        Fligne = np.zeros((3, 1))
        for barre in B:
            if barre.Ai.A == i:
                Fligne = np.add(Fligne, barre.Fij)
            if barre.Aj.A == i:
                Fligne = np.add(Fligne, barre.Fji)
        lignes.append(Fligne)
    F = np.vstack(lignes)
    for i in range(len(F)):
        F[i, 0] = F[i, 0] - cas[2][i]

    return F


def crea_matrice_rigidite(A, B):
    # création de la matrice de rigidité globale
    Kliste = []
    for li, noeud in enumerate(A):
        list_ligne = [np.zeros((3, 3))] * len(A)
        for co in range(len(A)):
            if li == co:
                Kmatr = np.zeros([3, 3])
                for ind_barre in noeud.barres_orig:
                    if B[ind_barre].Ai.A == li:
                        Kmatr = Kmatr + B[ind_barre].Kij
                for ind_barre in noeud.barres_arriv:
                    if B[ind_barre].Aj.A == li:
                        Kmatr = Kmatr + B[ind_barre].Kji
                list_ligne[co] = Kmatr

            else:
                inters_ij = trouve_commun(noeud.barres_orig, A[co].barres_arriv)
                inters_ji = trouve_commun(noeud.barres_arriv, A[co].barres_orig)
                if inters_ij >= 0:
                    Lmatr = B[inters_ij].Lij
                elif inters_ji >= 0:
                    Lmatr = B[inters_ji].Lji
                else:
                    Lmatr = np.zeros([3, 3])
                # for barre in B:
                #     if barre.Ai.A == li and barre.Aj.A == co:
                #         Lmatr = barre.Lij
                #         break
                #     if barre.Aj.A == li and barre.Ai.A == co:
                #         Lmatr = barre.Lji
                #         break
                list_ligne[co] = Lmatr

        kline = np.hstack(list_ligne)
        Kliste.append(kline)
    K = np.vstack(Kliste)
    return K


def def_noeud_barres(GEOM, sect_pot, sect_trav):
    hfait = GEOM["pente"] * GEOM["portee"] / 2 + GEOM["hpot"]

    # print("définition des noeuds et barres")
    # print(GEOM)
    tab_noeuds = [Node(0, 0, 0), Node(0, GEOM["hpot"], 1),
                  Node(GEOM["portee"] / 10, GEOM["hpot"] + GEOM["portee"] * GEOM["pente"] / 10, 2),
                  Node(GEOM["portee"] / 2, hfait, 3),
                  Node(GEOM["portee"] - GEOM["portee"] / 10,
                       GEOM["hpot"] + GEOM["portee"] * GEOM["pente"] / 10, 4),
                  Node(GEOM["portee"], GEOM["hpot"], 5), Node(GEOM["portee"], 0, 6)]
    # print(tab_noeuds[0].X)
    tab_barres = [Beam(tab_noeuds[0], tab_noeuds[1], IPE.dict_carac(sect_pot)),
                  Beam(tab_noeuds[1], tab_noeuds[2], jarret(sect_trav)),
                  Beam(tab_noeuds[2], tab_noeuds[3], IPE.dict_carac(sect_trav)),
                  Beam(tab_noeuds[3], tab_noeuds[4], IPE.dict_carac(sect_trav)),
                  Beam(tab_noeuds[4], tab_noeuds[5], jarret(sect_trav)),
                  Beam(tab_noeuds[5], tab_noeuds[6], IPE.dict_carac(sect_pot))]
    for noeud in tab_noeuds:
        noeud.indexe_barres(tab_barres)
    # print("barre 0, inertie : ",tab_barres[0].I)
    return tab_noeuds, tab_barres


def change_sections(barres, poteau, arba):
    dict_pot = IPE.dict_carac(poteau)
    dict_arb = IPE.dict_carac(arba)
    barres[0].mod_attr_resist(dict_pot)
    barres[5].mod_attr_resist(dict_pot)
    barres[2].mod_attr_resist(dict_arb)
    barres[3].mod_attr_resist(dict_arb)
    barres[1].mod_attr_resist(jarret(arba))
    barres[4].mod_attr_resist(jarret(arba))


def optimise_IPE(geom=GEOMTEST, charges=CHARGETEST):
    """trouve les IPE poteaux et traverse les plus légers
       exemple entrées

       GEOMTEST = {"hpot":325, "portee":1480, "pente":0.035}

       CHARGETEST = [("CP_", [-1.2, -1.2, -1.2, -1.2, -1.2, -1.2],
                      [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -1000, 0,
                       0, 0, 0, 0, 0, 0, 0, 0, 0]),
                     ("NEI_", [0, -2.1, -2.1, -2.1, -2.1, 0],
                      [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                       0, 0, 0, 0, 0, 0, 0, 0, 0]),
                     ("NEI_ACCI", [0, -4.2, -4.2, -4.2, -4.2, 0],
                      [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                       0, 0, 0, 0, 0, 0, 0, 0, 0]),
                     ("VENT_G_DI", [-2.4, .6, .6, .6, .6, .6],
                      [0, 0, 0, 500, 0, 0, 0, 0, 0, 0, 0, 0,
                       0, 0, 0, 500, 0, 0, 0, 0, 0])]


    """
    pas_poss = {"poteau": "pas de solution en IPE"}

    critere_tete_g = geom["hpot"] / 150
    critere_tete_d = geom["hpot"] / 150
    critere_fleche = geom["portee"] / 200

    # ordre = CP, N, N accidentelle, V
    COMBI_DEPL = [(1, 1, 0), (1, 1, .6), (1, 0, 1), (1, 0.5, 1)]
    COMBI_EFF = [(1.35, 1.5, 0, 0), (1.35, 1.5, 0, .9), (1.35, 0, 0, 1.5),
                 (1, 0, 0, 1.5), (1.35, 0.75, 0, 1.5), (1, 0, 1, 0)]

    ch_max_arb = charges[0][1][1] * 1.35 + charges[1][1][1] * 1.5

    wpl_min = abs(((ch_max_arb * geom["portee"] ** 2) / 12) / 2350)
    if wpl_min >= 3512:
        ipe_trou = "IPE 600"
    else:
        ipe_trou = IPE.trouve_premier("Wpl.y", wpl_min)
    # print("IPE trouvé par predim : ", ipe_trou)

    ipe_pot = IPE.trouve_decal(ipe_trou, -2)
    ipe_arba = IPE.trouve_decal(ipe_trou, -4)
    # print("IPE démarrage recherche : ", ipe_pot, ipe_arba)
    A, B = def_noeud_barres(geom, ipe_pot, ipe_arba)
    list_matr_F = []
    for cas in charges:
        list_matr_F.append(crea_matrice_force(len(A), B, cas))

    comp_crit = False

    while not comp_crit:

        resultats_non_pond = []

        if ipe_arba == "IPE 600":
            return pas_poss

        if ipe_arba == ipe_pot:
            ipe_pot = IPE.trouve_decal(ipe_pot, 1)
            ipe_arba = IPE.trouve_decal(ipe_pot, -4)

        else:
            ipe_arba = IPE.trouve_decal(ipe_arba, 1)

        # print("IPE pour entrée calcport : ", ipe_pot, ipe_arba)

        # print("essai", ipe_pot, ipe_arba)
        change_sections(B, ipe_pot, ipe_arba)
        K = crea_matrice_rigidite(A, B)
        list_matr_F[0] = crea_matrice_force(len(A), B, charges[0])
        for i, cas in enumerate(charges):
            # print(cas[0])
            resultats_non_pond.append((cas[0], calcport(A, B, K, list_matr_F[i], cas)))

        taux_max = 0

        depl_max_tete_g = 0
        depl_max_tete_d = 0
        fleche_max = 0

        for cas_vent in resultats_non_pond[3:]:
            # print("Cas de vent ", cas_vent[0])
            triplet_cas = resultats_non_pond[:2]
            triplet_cas.append(cas_vent)
            # print("triplet cas depl ")
            # for cas in triplet_cas:
            # print(cas[0])

            for combi in COMBI_DEPL:

                depl_de_combi_tete_g = 0
                depl_de_combi_tete_d = 0
                fleche_de_combi = 0

                for j, cas in enumerate(triplet_cas):
                    # print(ipe_pot," ",ipe_arba," ", cas[0])
                    # print (j, cas[0])
                    # print("valeur depl tete gauche ajoutée = ", cas[1]["depl_t_p_g"] )
                    depl_de_combi_tete_g += cas[1]["depl_t_p_g"] * combi[j]
                    depl_de_combi_tete_d += cas[1]["depl_t_p_d"] * combi[j]
                    fleche_de_combi += cas[1]["fleche_fait"] * combi[j]
                # print("combinaison ",combi," depl tete poteau gauche ", abs(depl_de_combi_tete_g))
                if abs(depl_de_combi_tete_g) > depl_max_tete_g:
                    depl_max_tete_g = abs(depl_de_combi_tete_g)

                if abs(depl_de_combi_tete_d) > depl_max_tete_d:
                    depl_max_tete_d = abs(depl_de_combi_tete_d)

                if abs(fleche_de_combi) > fleche_max:
                    fleche_max = abs(fleche_de_combi)

        comp_eff = True

        for cas_vent in resultats_non_pond[3:]:

            # print("Cas de vent ", cas_vent[0])
            quatu_cas = resultats_non_pond[:3]
            quatu_cas.append(cas_vent)
            # print("quatuor")
            # for cas in quatu_cas:
            # print(cas[0])

            for combi in COMBI_EFF:
                dico_taux_cum = dict(tx_mom_pot_g=0,
                                     tx_mom_renf_g=0,
                                     tx_mom_pied_arba_g=0,
                                     tx_mom_fait=0,
                                     tx_mom_pied_arba_d=0,
                                     tx_mom_renf_d=0,
                                     tx_mom_pot_d=0,
                                     tx_cis_pot_g=0,
                                     tx_cis_renf_g=0,
                                     tx_cis_pied_arba_g=0,
                                     tx_cis_pied_arba_d=0,
                                     tx_cis_renf_d=0,
                                     tx_cis_pot_d=0)
                # print(combi)
                for i, cas in enumerate(quatu_cas):
                    for cle, res in cas[1].items():
                        # print(cle)
                        if "tx" in cle:
                            dico_taux_cum[cle] += res * combi[i]
                            # print("taux non pond = ", round(res,2), "taux pond cum = ", round(dico_taux_cum[cle],2))
                for nom, valeur in dico_taux_cum.items():
                    if abs(valeur) > 1:
                        # print(ipe_pot, ipe_arba)
                        # print ("ens resu apres contrainte ",round(valeur,2), " pour ", nom)
                        comp_eff = False
                    elif abs(valeur) > taux_max:
                        taux_max = abs(valeur)

        # print(" flèche max = ", fleche_max, " p g = ", depl_max_tete_g, " p d = ", depl_max_tete_d)
        comp_crit = depl_max_tete_g < critere_tete_g and (
                depl_max_tete_d < critere_tete_d and fleche_max < critere_fleche)
        # print(comp_crit, comp_eff)
        comp_crit = comp_crit and comp_eff
        # print(comp_crit)

        # print (comp_crit_t_g)

        # print("Taux de contrainte max : {:5.2f}".format(taux_max))

    return dict(poteau=ipe_pot, traverse=ipe_arba,
                fleche=round(fleche_max * 10, 1),
                ratio_fleche=int(geom["portee"] / fleche_max),
                deplacement_gauche=round(depl_max_tete_g * 10, 1),
                deplacement_droite=round(depl_max_tete_d * 10, 1),
                depl_tete_pot=round(max(abs(depl_max_tete_d), abs(depl_max_tete_g)) * 10, 1),
                ratio_depl=int(geom["hpot"] / max(abs(depl_max_tete_d), abs(depl_max_tete_g))),
                taux_trav=round(taux_max, 1) * 100,
                masse=round(IPE.trouve_val(ipe_pot, "G") * geom["hpot"] * 0.02 \
                            + IPE.trouve_val(ipe_arba, "G") * geom["portee"] * 0.5 * 0.022 / cos(atan(geom["pente"])))
                )


def charge_et_sections(geom=GEOMTEST, localisation=LOCALITEST, cp=CPTEST):
    try:
        canton = chnv.trouve_canton(localisation["departement"], localisation["nom_commune"],
                                    localisation["ancien_nom_comm"])
        zones = chnv.trouve_zones_NV(localisation["departement"], canton)
    except Exception as e:
        return {"poteau": "problème de zonage"}, e
        # print(zones)
        # message = "OK pour les zones"
        # return {"poteau" : "problème de localisation"}, message

    cp_arba = -(cp["couv"] + cp["divers"] + 7) * geom["entraxe"] / 10000
    # print(cp_arba)
    try:
        charges_calc = [("CP_", [0, cp_arba, cp_arba, cp_arba, cp_arba, 0],
                         [0, 0, 0, 0, 0, 0,
                          0, 0, 0, 0, 0, 0,
                          0, 0, 0, 0, 0, 0,
                          0, 0, 0])] + chnv.charge_neige(zones[0], localisation["altitude"], geom) \
                       + chnv.charge_vent(zones[1], localisation["rugosite"], geom)
        # for cas in charges_calc:
        # chnv.affiche_cas(cas)
        # print("Temps de recherche charges = ", time.time() - START_TIME)
    except Exception as e:
        return {"poteau": "problème de localisation"}, e

    try:
        return optimise_IPE(geom, charges_calc), "OK"
    except Exception as e:
        return {"poteau": "problème de calcul"}, e


if __name__ == "__main__":

    # RESU = calcport()
    # print("")
    # print("-------Déplacements (mm)--------")
    # print("")

    # print("Tête poteau gauche : ", round(RESU["depl_t_p_g"]*10, 2))
    # print("Tête poteau droite : ", round(RESU["depl_t_p_d"]*10, 2))
    # print("Faîtage : ", round(RESU["fleche_fait"]*10, 2))

    GEOMTEST2 = {"hpot": 500, "portee": 400, "pente": 0.12, "longueur": 5500, "h_acro": 100, "entraxe": 500}

    CHARGETEST2 = [("CP_", [-1.2, -2.1, -2.1, -2.1, -2.1, -1.2],
                    [0, 0, 0, 0, 0, 0,
                     0, 0, 0, 0, 0, 0,
                     0, 0, 0, 0, 0, 0,
                     0, 0, 0]),
                   ("NEI_", [0, -3, -3, -3, -3, 0],
                    [0, 0, 0, 0, 0, 0,
                     0, 0, 0, 0, 0, 0,
                     0, 0, 0, 0, 0, 0,
                     0, 0, 0]),
                   ("NEI_ACCI", [0, -7.2, -7.2, -7.2, -7.2, 0],
                    [0, 0, 0, 0, 0, 0,
                     0, 0, 0, 0, 0, 0,
                     0, 0, 0, 0, 0, 0,
                     0, 0, 0]),
                   ("VENT_G_DI", [-3.8, 1.2, 1.2, .9, .9, 0],
                    [0, 0, 0, 700, 0, 0,
                     0, 0, 0, 0, 0, 0,
                     0, 0, 0, 466, 0, 0,
                     0, 0, 0]),
                   ("VENT_D_SI", [0.4, 0.4, 0.4, 0.4, 0.4, -.6],
                    [0, 0, 0, -0, 0, 0,
                     0, 0, 0, 0, 0, 0,
                     0, 0, 0, -0, 0, 0,
                     0, 0, 0])]

    # print(optimise_IPE(GEOMTEST2, CHARGETEST2))

    GEOMTEST3 = {"hpot": 325, "portee": 1470, "pente": .1, "longueur": 2680,
                 "entraxe": 670, "h_acro": 120}

    # zones = chnv.trouve_zones_NV({"nom_commune": "Ganges",
    # "ancien_nom_comm": "chaine",
    # "departement": "34",
    # "altitude": 120,
    # "rugosite":"chaine"})

    # CHARGETEST0 = [("CP_", [0, -1, -1, -1, -1, 0],
    # [0, 0, 0, 0, 0, 0,
    # 0, 0, 0, 0, 0, 0,
    # 0, 0, 0, 0, 0, 0,
    # 0, 0, 0]),
    # ("NEI_", [0, 0, 0, 0, 0, 0],
    # [0, 0, 0, 0, 0, 0,
    # 0, 0, 0, 0, 0, 0,
    # 0, 0, 0, 0, 0, 0,
    # 0, 0, 0]),
    # ("NEI_ACCI", [0, 0, 0, 0, 0, 0],
    # [0, 0, 0, 0, 0, 0,
    # 0, 0, 0, 0, 0, 0,
    # 0, 0, 0, 0, 0, 0,
    # 0, 0, 0])
    # ]

    # CHARGETEST3 = [("CP_", [0, 0, 0, 0, 0, 0],
    # [0, 0, 0, 0, 0, 0,
    # 0, 0, 0, 0, 0, 0,
    # 0, 0, 0, 0, 0, 0,
    # 0, 0, 0])] + chnv.charge_neige(zones[0], 120, GEOMTEST3) \
    # + chnv.charge_vent(zones[1], "IIIb", GEOMTEST3)

    LOCALITEST3 = {"nom_commune": "Ganges",
                   "ancien_nom_comm": "chaine",
                   "departement": "34",
                   "altitude": 120,
                   "rugosite": "IIIb"}

    CPTEST3 = {"couv": 21, "divers": 3}

    # chnv.affiche_cas(CHARGETEST3[3])
    # print(optimise_IPE(GEOMTEST3, CHARGETEST0))

    # print(optimise_IPE())

    # for cas in CHARGETEST3:
    # resu_test = calcport(GEOMTEST3, cas,
    # sect_pot="IPE 270", sect_trav="IPE 270")
    # print(cas[0])
    # for cle, val in resu_test.items():
    # print("{} : {:5.2f}".format(cle,val))
# --- Configuration du Logging ---
    log_directory_name = "logs"
    log_filename = "calculation_timing.log"
    script_dir = pathlib.Path(__file__).parent
    log_dir = script_dir / log_directory_name
    log_filepath = log_dir / log_filename

    # Créer le dossier logs s'il n'existe pas
    log_dir.mkdir(parents=True, exist_ok=True)

    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    logging.basicConfig(filename=log_filepath,
                        level=logging.INFO,
                        format=log_format,
                        encoding='utf-8',
                        datefmt=date_format
                       )
    # --- Fin Configuration Logging ---

    logging.info("===== Début du Lancement Calcul =====")

    # --- Récupérer les données d'entrée ---
    logging.info("Préparation des données d'entrée...")
    geomtest3_formate = pprint.pformat(GEOMTEST3, indent=2)
    cptest3_formate = pprint.pformat(CPTEST3, indent=2)
    localitest3_formate = pprint.pformat(LOCALITEST3, indent=2)
    logging.info(f"Données de géométrie : \n{geomtest3_formate}")
    logging.info(f"Données de chargement : \n{cptest3_formate}")
    logging.info(f"Donnés de localisation : \n{localitest3_formate}")
    # ...

    # --- Chronométrage ---
    logging.info("Début du calcul RDM.")
    start_time = time.perf_counter()

    try:
        resultat_calcul = charge_et_sections(GEOMTEST3, LOCALITEST3, CPTEST3)


        end_time = time.perf_counter()
        duration_ms = (end_time - start_time) * 1000

        resultat_formate = pprint.pformat(resultat_calcul, indent=2)
        logging.info(f"Résultat du calcul : \n{resultat_formate}")

        logging.info(f"Calcul RDM terminé avec succès.")
        logging.info(f"Durée du calcul principal : {duration_ms:.3f} ms")

    except Exception as e:
        logging.error("Une erreur est survenue pendant le calcul.", exc_info=True)

    logging.info("===== Fin du Lancement Calcul =====")

  
