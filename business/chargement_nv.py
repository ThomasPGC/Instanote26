#!/usr/bin/python3
# coding: utf-8

"""Module pour créer les charges de neige et de vent."""

import os
import csv
from math import sin, cos, atan, degrees, log, sqrt, pi, e

# from numpy import interp as interpole

module_dir = os.path.abspath(os.path.dirname(__file__))

vent_base = {"1": 22, "2": 24, "3": 26, "4": 28}

coeff_zone_rugo = {"0": {"z0": 0.005, "zmin": 1, "kr": 0.162, "KI": 1},
                   "II": {"z0": 0.05, "zmin": 2, "kr": 0.19, "KI": 1},
                   "IIIa": {"z0": 0.2, "zmin": 5, "kr": 0.209, "KI": 0.97},
                   "IIIb": {"z0": 0.5, "zmin": 9, "kr": 0.223, "KI": 0.92},
                   "IV": {"z0": 1, "zmin": 15, "kr": 0.234, "KI": 0.85}
                   }


def interpole(x, dx, fx, d, f):
    return d + (x - dx) * (f - d) / (fx - dx)


def affiche_cas(cas):
    print(cas[0])
    print("charges linéaires")
    for lin in cas[1][1:5]:
        print("{:5.2f} ".format(lin, 2), end=""),
    print("\n{:5.2f}             {:5.2f}".format(cas[1][0], cas[1][5]))
    print("charges ponctuelles")
    for i in range(len(cas[2]) // 3):
        print("{:5.1f} {:5.1f} {:5.1f}".format(cas[2][i * 3], cas[2][i * 3 + 1], cas[2][i * 3 + 2])),


def pondere_FG_longpan(F, G, e, entraxe):
    if e / 4 <= entraxe / 2:
        return G
    elif e / 4 <= 1.5 * entraxe:
        return (F * (e / 4 - entraxe / 2) + G * (entraxe - (e / 4 - entraxe / 2))) / entraxe
    else:
        return F


def repart_charge_surpl(ch_base, ch_surpl, long_surpl, long_b1, long_b2):
    p = ch_surpl - ch_base
    if long_surpl <= long_b1:
        a = long_surpl
        l = long_b1
        reac_1 = p * a * (l - a / 2) / l
        reac_2 = p * a * a / (2 * l)
        reac_3 = 0

    else:
        a = long_surpl - long_b1
        l = long_b2
        reac_1 = p * long_b1 / 2
        reac_2 = p * long_b1 / 2 + p * a * (l - a / 2) / l
        reac_3 = p * a * a / (2 * l)
    return (reac_1, reac_2, reac_3)


def trouve_canton(departement, nom_commune, ancienne_commune):
    """Trouve un canton à partir de l'adresse."""
    commune = nom_commune.split()[-1]
    if ancienne_commune != "":
        anc_comm = ancienne_commune.split()[-1]
    else:
        anc_comm = ""
    # print(" Commune: {}, ancienne commune : {}".format(commune, anc_comm))
    if departement[0] == "0":
        departement = departement[1]
    with open(os.path.join(module_dir, "./france1999cantons.csv"), encoding='cp850') as cantons:
        read_csv = csv.DictReader(cantons, delimiter=',')
        for row in read_csv:
            if (row["DEP,C,3"][:2] == departement and
                    (row["NCCENR,C,70"] == commune
                     or row["NCCENR,C,70"] == anc_comm)):
                return row["NCCCT,C,70"]
    return None


def trouve_zones_NV(dep, canton):
    """Trouve les zones de neige et de vent."""
    with open(os.path.join(module_dir, "./DEP_NV.csv"), encoding='cp850') as liste_zones:
        read_csv = csv.DictReader(liste_zones, delimiter=',')
        for row in read_csv:
            if row["dep"][:2] == dep:
                if canton in row["cantons neige 2"]:
                    zone_neige = row["zone neige 2"]
                elif canton in row["cantons neige 3"]:
                    zone_neige = row["zone neige 3"]
                else:
                    zone_neige = row["Zone neige 1"]

                if canton in row["cantons vent 2"]:
                    zone_vent = row["zone vent 2"]
                elif canton in row["cantons vent 3"]:
                    zone_vent = row["zone vent 3"]
                else:
                    zone_vent = row["Zone vent 1"]

    return (zone_neige, zone_vent)


def charge_neige(z_nei, alti, geom):
    neiges_sol = {"A1": (45, 0), "A2": (45, 100),
                  "B1": (55, 100), "B2": (55, 135),
                  "C1": (65, 0), "C2": (65, 135),
                  "D": (90, 180), "E": (140, 0)}

    angle_toit = degrees(atan(geom["pente"]))
    entraxe = geom["entraxe"] / 100
    portee = geom["portee"] / 100
    h_acro = geom["h_acro"] / 100

    def neige_alti(z_nei, alti):
        if z_nei == "E":
            if alti < 200:
                return neiges_sol[z_nei][0]
            elif alti < 500:
                return neiges_sol[z_nei][0] + 1.5 * alti / 10 - 30
            elif alti < 1000:
                return neiges_sol[z_nei][0] + 3.5 * alti / 10 - 130
            else:
                return neiges_sol[z_nei][0] + 7 * alti / 10 - 480
        else:
            if alti < 200:
                return neiges_sol[z_nei][0]
            elif alti < 500:
                return neiges_sol[z_nei][0] + alti / 10 - 20
            elif alti < 1000:
                return neiges_sol[z_nei][0] + 1.5 * alti / 10 - 45
            else:
                return neiges_sol[z_nei][0] + 3.5 * alti / 10 - 245

    def mu_deux(angle_toit):
        if angle_toit <= 30:
            return 0.8
        elif angle_toit <= 60:
            return 0.8 * (60 - angle_toit) / 30
        else:
            return 0

    ch_bar_norm = entraxe * neige_alti(z_nei, alti) * mu_deux(angle_toit) / 100
    ch_bar_acci = entraxe * neiges_sol[z_nei][1] * mu_deux(angle_toit) / 100

    # print("Charge neige arba normale = {:5.1f}, charge neige arba accidentelle = {:5.1f}".format(ch_bar_norm, ch_bar_acci))

    ch_noeud_pot = entraxe * 20 * min(2, portee / 20)
    ch_noeud_jar = entraxe * 20 * (2 - min(2, portee / 20))

    # la longueur d'accumulation est prise égale à 5 m
    # le coeff mu d'accumulation est pris égal à 1,6
    # la pente de l'accumulation est donc de (1,6 - 0,8) / 5 = 0,16

    if h_acro > 0.2:
        ch_noeud_accu_pot = ch_bar_norm * 100 * 0.16 * (5 - portee / 40) * portee / 20
        ch_noeud_accu_jar = max(((ch_bar_norm * 100 * 5 / 2) - ch_noeud_accu_pot), 0)
    else:
        ch_noeud_accu_pot = 0
        ch_noeud_accu_jar = 0

    charges_neige = ("NEI_", [0, -ch_bar_norm, -ch_bar_norm, -ch_bar_norm, -ch_bar_norm, 0],
                     [0, 0, 0,
                      0, -ch_noeud_pot - ch_noeud_accu_pot, 0,
                      0, -ch_noeud_jar - ch_noeud_accu_jar, 0,
                      0, 0, 0,
                      0, -ch_noeud_jar - ch_noeud_accu_jar, 0,
                      0, -ch_noeud_pot - ch_noeud_accu_pot, 0,
                      0, 0, 0])

    charges_acci = ("NEI_ACCI", [0, -ch_bar_acci, -ch_bar_acci, -ch_bar_acci, -ch_bar_acci, 0],
                    [0, 0, 0,
                     0, -ch_noeud_pot, 0,
                     0, -ch_noeud_jar, 0,
                     0, 0, 0,
                     0, -ch_noeud_jar, 0,
                     0, -ch_noeud_pot, 0,
                     0, 0, 0])

    return [charges_neige, charges_acci]


def charge_vent(z_vent, rugo, geom):
    pente = geom["pente"]
    entraxe = geom["entraxe"] / 100
    portee = geom["portee"] / 100
    longueur = geom["longueur"] / 100
    h_acro = geom["h_acro"] / 100
    hpot = geom["hpot"] / 100

    qpz = calc_qpz(coeff_zone_rugo, h_acro, hpot, rugo, vent_base, z_vent)
    ch_l_base = entraxe * qpz

    Cis = 0.2
    Cid = -0.3

    def vent_longpan(b=longueur, d=portee, h=max(h_acro + hpot, hpot + pente * portee / 2), entraxe=entraxe,
                     pente=pente, hp=h_acro, z_vent=z_vent, rugo=rugo):

        e_EC = min(b, 2 * h)

        D = E = F = G = H = I = J = 0
        Fneg = Fpos = Gneg = Gpos = Hneg = Hpos = 0
        Ineg = Ipos = Jneg = Jpos = 0

        # coefficients murs

        kdc = 0.85
        cscd = calc_cscd(h, b, z_vent, rugo)

        if h / d >= 5:
            D = 0.8
            E = -0.7
            kdc = 1
        elif h / d >= 1:
            D = 0.8
            E = interpole(h / d, 1, 5, -0.5, -0.7)
            kdc = interpole(h / d, 1, 5, 0.85, 1)
        elif h / d >= 0.25:
            D = interpole(h / d, .25, 1, 0.7, 0.8)
            E = interpole(h / d, .25, 1, -0.3, -0.5)
        else:
            D = .7
            E = -.3

        # print(D,E)
        # print('h = {:5.2f}, d = {:5.2f}, h/d = {:5.2f}, kdc = {:5.2f}'.format(h,d,h/d,kdc))

        ch_pot_av_di = qpz * entraxe * (-D * kdc * cscd + Cid) / 100
        ch_pot_sv_di = qpz * entraxe * (E * kdc * cscd - Cid) / 100

        # print(round(ch_pot_av_di,2),round(ch_pot_sv_di,2))

        ch_pot_av_si = qpz * entraxe * (-D * kdc * cscd + Cis) / 100
        ch_pot_sv_si = qpz * entraxe * (E * kdc * cscd - Cis) / 100

        # coefficients acrotères

        coef_acro_av = pondere_FG_longpan(2, 1.5, e_EC, entraxe)

        ch_noeud_pot_av = qpz * cscd * entraxe * hp * coef_acro_av
        mom_tet_pot_av = -100 * ch_noeud_pot_av * hp / 2
        ch_noeud_pot_sv = qpz * cscd * entraxe * hp
        mom_tet_pot_sv = -100 * ch_noeud_pot_sv * hp / 2

        # coefficients versants

        angle_toit = degrees(atan(pente))
        angle_rad = atan(pente)

        if angle_toit < 5:
            H = -0.7
            Ipos = 0.2
            Ineg = -0.2

            if hp / h <= .025:
                F = -1.6
                G = -1.1
            elif hp / h <= 0.05:
                F = interpole(hp / h, 0.025, 0.05, -1.6, -1.4)
                G = interpole(hp / h, 0.025, 0.05, -1.1, -0.9)
            elif hp / h < .1:
                F = interpole(hp / h, 0.05, 0.1, -1.4, -1.2)
                G = interpole(hp / h, 0.05, 0.1, -0.9, -0.8)
            else:
                F = -1.2
                G = -0.8

            FG = pondere_FG_longpan(F, G, e_EC, entraxe)

            # print("------ calcul FG angle < 5 ------")
            # print("F = {:5.2f}, G = {:5.2f}, FG = {:5.2f}, H = {:5.2f}, sur {:5.2f} m".format(F,G,FG,H,e/10))

            eff_tet_pot = -repart_charge_surpl(H, FG, e_EC / 10, portee / 10, portee * 4 / 10)[0]
            eff_fin_jarr = -repart_charge_surpl(H, FG, e_EC / 10, portee / 10, portee * 4 / 10)[1]
            eff_fait = -repart_charge_surpl(H, FG, e_EC / 10, portee / 10, portee * 4 / 10)[2]

            # print("Effort ajouté par FG sur H en tête de poteau = {:5.1f}".format(eff_tet_pot* ch_l_base))
            # print("Effort ajouté par FG sur H en extrémité de jarret = {:5.1f}".format(eff_fin_jarr * ch_l_base))
            # print("Effort ajouté par FG sur H au faitage = {:5.1f}".format(eff_fait * ch_l_base))

            if e_EC / 2 < d / 2:
                surpl_Ineg = (
                    eff_tet_pot -
                    repart_charge_surpl(H, Ineg, min(d / 2, d / 2 - e_EC / 2), portee * 4 / 10, portee / 10)[
                        2],
                    eff_fin_jarr -
                    repart_charge_surpl(H, Ineg, min(d / 2, d / 2 - e_EC / 2), portee * 4 / 10, portee / 10)[1],
                    eff_fait - repart_charge_surpl(H, Ineg, min(d / 2, d / 2 - e_EC / 2), portee * 4 / 10, portee / 10)[
                        0],
                    0)

                surpl_Ipos = (
                    eff_tet_pot -
                    repart_charge_surpl(H, Ipos, min(d / 2, d / 2 - e_EC / 2), portee * 4 / 10, portee / 10)[
                        2],
                    eff_fin_jarr -
                    repart_charge_surpl(H, Ipos, min(d / 2, d / 2 - e_EC / 2), portee * 4 / 10, portee / 10)[1],
                    eff_fait - repart_charge_surpl(H, Ipos, min(d / 2, d / 2 - e_EC / 2), portee * 4 / 10, portee / 10)[
                        0],
                    0)
            else:
                surpl_Ineg = (eff_tet_pot,
                              eff_fin_jarr,
                              eff_fait -
                              repart_charge_surpl(Ineg, H, min(d / 2, e_EC / 2 - d / 2), portee * 4 / 10, portee / 10)[
                                  0],
                              repart_charge_surpl(Ineg, H, min(d / 2, e_EC / 2 - d / 2), portee * 4 / 10, portee / 10)[
                                  1])

                surpl_Ipos = (eff_tet_pot,
                              eff_fin_jarr,
                              eff_fait -
                              repart_charge_surpl(Ipos, H, min(d / 2, e_EC / 2 - d / 2), portee * 4 / 10, portee / 10)[
                                  0],
                              repart_charge_surpl(Ipos, H, min(d / 2, e_EC / 2 - d / 2), portee * 4 / 10, portee / 10)[
                                  1])

            ch_arba_av_di = qpz * 0.4 * entraxe / 100
            ch_arba_av_si = qpz * 0.9 * entraxe / 100

            ch_arba_sv_di_Ineg = -qpz * 0.1 * entraxe / 100
            ch_arba_sv_si_Ineg = qpz * 0.4 * entraxe / 100

            ch_arba_sv_di_Ipos = -qpz * 0.5 * entraxe / 100
            ch_arba_sv_si_Ipos = 0

            # print("longueur de H = {:5.1f}, longueur versant = {:5.1f}".format(e/2, d/2))
            # print("surpl Ineg ", surpl_Ineg)
            # print("surpl Ipos ", surpl_Ipos)

            vent_gauche_di_Ineg = ("VEN_G_D_neg",
                                   [ch_pot_av_di, ch_arba_av_di, ch_arba_av_di,
                                    ch_arba_sv_di_Ineg, ch_arba_sv_di_Ineg,
                                    ch_pot_sv_di],
                                   [0, 0, 0,
                                    ch_noeud_pot_av - surpl_Ineg[0] * ch_l_base * sin(angle_rad),
                                    surpl_Ineg[0] * ch_l_base * cos(angle_rad),
                                    mom_tet_pot_av,
                                    -surpl_Ineg[1] * ch_l_base * sin(angle_rad),
                                    surpl_Ineg[1] * ch_l_base * cos(angle_rad),
                                    0,
                                    -surpl_Ineg[2] * ch_l_base * sin(angle_rad),
                                    surpl_Ineg[2] * ch_l_base * cos(angle_rad),
                                    0,
                                    -surpl_Ineg[3] * ch_l_base * sin(angle_rad),
                                    surpl_Ineg[3] * ch_l_base * cos(angle_rad),
                                    0,
                                    ch_noeud_pot_sv, 0, mom_tet_pot_sv,
                                    0, 0, 0])
            return [vent_gauche_di_Ineg]

        else:
            if angle_toit < 15:
                Fneg = interpole(angle_toit, 5, 15, -1.7, -0.9)
                Fpos = interpole(angle_toit, 5, 15, 0, 0.2)
                Gneg = interpole(angle_toit, 5, 15, -1.2, -0.8)
                Gpos = interpole(angle_toit, 5, 15, 0, 0.2)
                Hneg = interpole(angle_toit, 5, 15, -0.6, -0.3)
                Hpos = interpole(angle_toit, 5, 15, 0, 0.2)
                Ineg = interpole(angle_toit, 5, 15, -0.6, -0.4)
                Ipos = interpole(angle_toit, 5, 15, -0.6, 0)
                Jneg = interpole(angle_toit, 5, 15, -0.6, -1)
                Jpos = interpole(angle_toit, 5, 15, 0.2, 0)

            elif angle_toit < 30:
                Fneg = interpole(angle_toit, 15, 30, -0.9, -0.5)
                Fpos = interpole(angle_toit, 15, 30, 0.2, 0.7)
                Gneg = interpole(angle_toit, 15, 30, -0.8, -0.5)
                Gpos = interpole(angle_toit, 15, 30, 0.2, 0.7)
                Hneg = interpole(angle_toit, 15, 30, -0.3, -0.2)
                Hpos = interpole(angle_toit, 15, 30, 0.2, 0.4)
                Ineg = -0.4
                Ipos = 0
                Jneg = interpole(angle_toit, 15, 30, -1, -0.5)
                Jpos = 0

            elif angle_toit < 45:
                Fneg = interpole(angle_toit, 30, 45, -0.5, 0)
                Fpos = 0.7
                Gneg = interpole(angle_toit, 30, 45, -0.5, 0)
                Gpos = 0.7
                Hneg = interpole(angle_toit, 30, 45, -0.2, 0)
                Hpos = interpole(angle_toit, 30, 45, 0.4, 0.6)
                Ineg = interpole(angle_toit, 30, 45, -0.4, -0.2)
                Ipos = 0
                Jneg = interpole(angle_toit, 30, 45, -0.5, -0.3)
                Jpos = 0

            elif angle_toit < 60:
                F = 0.7
                G = 0.7
                H = interpole(angle_toit, 45, 60, 0.6, 0.7)
                I = -0.2
                J = -0.3

            elif angle_toit < 75:
                F = interpole(angle_toit, 60, 75, 0.7, 0.8)
                G = interpole(angle_toit, 60, 75, 0.7, 0.8)
                H = interpole(angle_toit, 60, 75, 0.7, 0.8)
                I = -0.2
                J = -0.3

            else:
                F = 0.8
                G = 0.8
                H = 0.8
                I = -0.2
                J = -0.3

            if F != 0:
                FG = pondere_FG_longpan(F, G, e_EC, entraxe)
                print("F = {:.2f}, G = {:.2f}, FG = {:.2f}".format(F, G, FG))
                surpl_FG = (repart_charge_surpl(H, FG, e_EC / 10, portee / 10, 4 * portee / 10))
                # print("surplus FG, poteau = {:.1f}, sur le jarret = {:.1f}, au faitage = {:.1f}".format(
                # surpl_FG[0]*ch_l_base,surpl_FG[1]*ch_l_base,surpl_FG[2]*ch_l_base))
                surpl_J = (repart_charge_surpl(I, J, e_EC / 10, 4 * portee / 10, portee / 10))
                # print("surplus J, a faitage = {:.1f}; sur le jarret = {:.1f}".format(
                # surpl_J[0]*ch_l_base,surpl_J[1]*ch_l_base))
                vent_gauche_di = ("VEN_G_D_",
                                  [ch_pot_av_di,
                                   ch_l_base * (-H + Cid) / 100,
                                   ch_l_base * (-H + Cid) / 100,
                                   ch_l_base * (-I + Cid) / 100,
                                   ch_l_base * (-I + Cid) / 100,
                                   ch_pot_sv_di],
                                  [0, 0, 0,
                                   ch_noeud_pot_av - surpl_FG[0] * ch_l_base * sin(angle_rad),
                                   surpl_FG[0] * ch_l_base * cos(angle_rad),
                                   mom_tet_pot_av,
                                   -surpl_FG[1] * ch_l_base * sin(angle_rad),
                                   surpl_FG[1] * ch_l_base * cos(angle_rad),
                                   0,
                                   (-surpl_FG[2] - surpl_J[0]) * ch_l_base * sin(angle_rad),
                                   (-surpl_FG[2] - surpl_J[0]) * ch_l_base * cos(angle_rad),
                                   0,
                                   -surpl_J[1] * ch_l_base * sin(angle_rad),
                                   -surpl_J[1] * ch_l_base * cos(angle_rad),
                                   0,
                                   ch_noeud_pot_sv - surpl_J[2] * ch_l_base * sin(angle_rad),
                                   -surpl_J[2] * ch_l_base * cos(angle_rad),
                                   mom_tet_pot_sv,
                                   0, 0, 0])

                return [vent_gauche_di]
            else:
                vent_gauche_di = []
                FGpos = pondere_FG_longpan(Fpos, Gpos, e_EC, entraxe)
                FGneg = pondere_FG_longpan(Fneg, Gneg, e_EC, entraxe)
                coeff_av = (("_pos", FGpos, Hpos), ("_neg", FGneg, Hneg))
                coeff_sv = (("_pos", Ipos, Jpos), ("_neg", Ineg, Jneg))
                for co in coeff_av:
                    for eff in coeff_sv:
                        surpl_FG = (repart_charge_surpl(co[2], co[1], e_EC / 10, portee / 10, 4 * portee / 10))
                        surpl_J = (repart_charge_surpl(eff[1], eff[2], e_EC / 10, 4 * portee / 10, portee / 10))
                        vent_gauche_di.append(
                            ("VEN_G_D" + co[0] + eff[0],
                             [ch_pot_av_di,
                              ch_l_base * (-co[2] + Cid) / 100,
                              ch_l_base * (-co[2] + Cid) / 100,
                              ch_l_base * (-eff[1] + Cid) / 100,
                              ch_l_base * (-eff[1] + Cid) / 100,
                              ch_pot_sv_di],
                             [0, 0, 0,
                              ch_noeud_pot_av - surpl_FG[0] * ch_l_base * sin(angle_rad),
                              surpl_FG[0] * ch_l_base * cos(angle_rad),
                              mom_tet_pot_av,
                              -surpl_FG[1] * ch_l_base * sin(angle_rad),
                              surpl_FG[1] * ch_l_base * cos(angle_rad),
                              0,
                              (-surpl_FG[2] - surpl_J[0]) * ch_l_base * sin(angle_rad),
                              (-surpl_FG[2] - surpl_J[0]) * ch_l_base * cos(angle_rad),
                              0,
                              -surpl_J[1] * ch_l_base * sin(angle_rad),
                              -surpl_J[1] * ch_l_base * cos(angle_rad),
                              0,
                              ch_noeud_pot_sv - surpl_J[2] * ch_l_base * sin(angle_rad),
                              -surpl_J[2] * ch_l_base * cos(angle_rad),
                              mom_tet_pot_sv,
                              0, 0, 0]
                             ))
                return vent_gauche_di

        return 0

    def vent_pignon(b=portee, d=longueur, h=max(h_acro + hpot, hpot + pente * portee / 2), entraxe=entraxe, pente=pente,
                    hp=h_acro):

        e = min(b, 2 * h)

        A = B = C = F = G = H = I = 0
        Ineg = Ipos = 0

        # coefficients murs

        A = -1.2
        B = -0.8
        C = -0.5

        vent_desc_terr = []

        long_A = long_B = long_C = 0

        if e / 5 > 1.5 * entraxe:
            long_A = entraxe
        elif e / 5 > .5 * entraxe:
            long_A = e / 5 - 0.5 * entraxe
            if e > 1.5 * entraxe:
                long_B = entraxe - long_A
            else:
                lon_B = 4 * e / 5
        else:
            if e > 1.5 * entraxe:
                long_B = entraxe
            elif e > .5 * entraxe:
                long_B = e - .5 * entraxe
        long_C = entraxe - long_A - long_B

        ABC = (A * long_A + B * long_B + C * long_C) / entraxe

        # print("Entraxe = {:3.1f}, demi entraxe = {:3.1f}, fin entraxe = {:3.1f}".format(entraxe,0.5*entraxe,1.5*entraxe))
        # print("e = {:3.1f}, e/5 = {:3.1f}, 4e/5 = {:3.1f}".format(e,e/5,4*e/5))
        # print("Long A = {:3.1f}, long B = {:3.1f}, long C = {:3.1f}, coeff ABC = {:3.2f}".format(long_A,long_B,long_C,ABC))

        ch_pot_si = -(ABC - Cis) * ch_l_base / 100

        # pas d'influence sur les acrotères pour le vent pignon

        # coefficients versants

        angle_toit = degrees(atan(pente))

        if angle_toit < 5:
            H = -0.7
            Ipos = 0.2
            I = -0.2

            if hp / h <= .025:
                F = -1.6
                G = -1.1
            elif hp / h <= 0.05:
                F = interpole(hp / h, 0.025, 0.05, -1.6, -1.4)
                G = interpole(hp / h, 0.025, 0.05, -1.1, -0.9)
            elif hp / h < .1:
                F = interpole(hp / h, 0.05, 0.1, -1.4, -1.2)
                G = interpole(hp / h, 0.05, 0.1, -0.9, -0.8)
            else:
                F = -1.2
                G = -0.8

            long_Ipot = d - 0.5 * entraxe - 0.5 * e
            if long_Ipot > 0:
                if long_Ipot < entraxe:
                    Ipos = (Ipos * long_Ipot + H * (entraxe - long_Ipot)) / entraxe

                ###print("Longueur = {:3.1f}, demi entraxe = {:3.1f}, e/2 = {:3.1f}".format(d,0.5*entraxe,e/2))
                ###print("Long I restant = {:3.1f}, I pos = {:3.1f}".format(long_Ipot,Ipos))

                if Ipos > -0.3:
                    ch_pot_di = -(ABC - Cid) * ch_l_base / 100
                    ch_VP_desc_arba = -ch_l_base * (Ipos - Cid) / 100
                    vent_desc_terr = [("VEN_P_desc",
                                       [ch_pot_di, ch_VP_desc_arba, ch_VP_desc_arba,
                                        ch_VP_desc_arba, ch_VP_desc_arba, ch_pot_di],
                                       [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])]
                    # affiche_cas(vent_desc_terr[0])

        elif angle_toit < 15:
            F = interpole(angle_toit, 5, 15, -1.6, -1.3)
            G = -1.3
            H = interpole(angle_toit, 5, 15, -0.7, -0.6)
            I = interpole(angle_toit, 5, 15, -0.6, -0.5)


        elif angle_toit < 30:
            F = interpole(angle_toit, 15, 30, -1.3, -1.1)
            G = interpole(angle_toit, 15, 30, -1.3, -1.4)
            H = interpole(angle_toit, 15, 30, -0.6, -0.8)
            I = -0.5

        elif angle_toit < 45:
            F = -1.1
            G = -1.4
            H = interpole(angle_toit, 15, 30, -0.8, -0.9)
            I = -0.5

        elif angle_toit < 60:
            F = -1.1
            G = interpole(angle_toit, 15, 30, -1.4, -1.2)
            H = interpole(angle_toit, 15, 30, -0.9, -0.8)
            I = -0.5

        else:
            F = -1.1
            G = -1.2
            H = -0.8
            I = -0.5

        FG = (F * e * 0.5 + G * (b - e * 0.5)) / b
        # print("b = {:3.1f}, e/2 = {:3.1f}, reste G = {:3.1f}".format(b,0.5*e,b - e * 0.5))
        # print("F = {:3.1f}, G = {:3.1f}, FG = {:3.2f}".format(F,G,FG))

        long_FG = long_H = long_I = 0

        if e / 10 > 1.5 * entraxe:
            long_FG = entraxe
        elif e / 10 > .5 * entraxe:
            long_FG = e / 10 - 0.5 * entraxe
            if e / 2 > 1.5 * entraxe:
                long_H = entraxe - long_FG
            else:
                long_H = 4 * e / 10
        else:
            if e / 2 > 1.5 * entraxe:
                long_H = entraxe
            elif e / 2 > .5 * entraxe:
                long_H = e / 2 - .5 * entraxe
        long_I = entraxe - long_FG - long_H

        FGHI = (FG * long_FG + H * long_H + I * long_I) / entraxe

        # print("H = {:3.2f}, I = {:3.2f}".format(H,I))
        # print("Entraxe = {:3.1f}, demi entraxe = {:3.1f}, fin entraxe = {:3.1f}".format(entraxe,0.5*entraxe,1.5*entraxe))
        # print("e/2 = {:3.1f}, e/10 = {:3.1f}, 4e/10 = {:3.1f}".format(e/2,e/10,4*e/10))
        # print("Long FG = {:3.1f}, long H = {:3.1f}, long I = {:3.1f}, coeff FGHI = {:3.2f}".format(long_FG,long_H,long_I,FGHI))

        ch_arba_si = -(FGHI - Cis) * ch_l_base / 100
        # print("cis = {:3.1f}, somme coeffs = {:3.2f}, charge arba ascendant = {:3.1f}".format(Cis, FGHI-Cis,ch_arba_si))
        vent_pi_surpr = [("VEN_P_SI",
                          [ch_pot_si, ch_arba_si, ch_arba_si,
                           ch_arba_si, ch_arba_si, ch_pot_si],
                          [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])]
        # affiche_cas(vent_pi_surpr[0])

        return vent_pi_surpr + vent_desc_terr

    # print(vent_longpan())
    # print(vent_longpan())

    return vent_longpan() + vent_pignon()


def calc_qpz(coeff_zone_rugo, h_acro, hpot, rugo, vent_base, z_vent):
    c_rug = coeff_zone_rugo[rugo]
    crz = c_rug["kr"] * log(max(hpot + h_acro, c_rug["zmin"]) / c_rug["z0"])
    Vmz = vent_base[z_vent] * crz
    Ivz = c_rug["KI"] / log(max(hpot + h_acro, c_rug["zmin"]) / c_rug["z0"])
    qpz = (1 + 7 * Ivz) * 0.5 * 1.225 * Vmz * Vmz / 10
    return qpz


def calc_cscd(h, b, z_vent, rugo, coeff_zone_rugo=coeff_zone_rugo, vent_base=vent_base):
    """d'après CTICM, Danielle Clavaud, Revue construction métallique 4-2011, pp. 113-116"""
    zs = 0.6 * h
    n1x = 46 / h
    c_rug = coeff_zone_rugo[rugo]
    z0 = c_rug["z0"]
    crzs = c_rug["kr"] * log(max(zs, c_rug["zmin"]) / c_rug["z0"])
    Vmzs = vent_base[z_vent] * crzs
    Lzs = 300 * (zs / 200) ** (0.67 + 0.05 * log(z0))

    fLzsn1x = n1x * Lzs / Vmzs
    SLzsn1x = 6.8 * fLzsn1x / (1 + 10.2 * fLzsn1x) ** (5 / 3)
    nub = 4.6 * b * fLzsn1x / Lzs
    Rbnub = 1 / nub - (1 - e ** -2 * nub) / (2 * nub ** 2)
    nuh = 4.6 * h * fLzsn1x / Lzs
    Rhnuh = 1 / nuh - (1 - e ** -2 * nuh) / (2 * nuh ** 2)
    R2 = (pi ** 2 / 0.1) * SLzsn1x * Rhnuh * Rbnub
    B2 = 1 / (1 + 0.9 * ((b + h) / Lzs) ** 0.63)
    v = max(0.08, n1x * sqrt((R2 / (B2 + R2))))
    kp = sqrt(2 * log(600 * v)) + 0.6 / sqrt(2 * log(600 * v))
    Ivzs = c_rug["KI"] / log(max(zs, c_rug["zmin"]) / c_rug["z0"])
    cscd = (1 + 2 * kp * Ivzs * sqrt(B2 + R2)) / (1 + 7 * Ivzs)

    return cscd


if __name__ == "__main__":
    # print(trouve_zones_NV("91", trouve_canton("91", "Les Ulis", "")))

    GEOMTEST3 = {"hpot": 325, "portee": 1470, "pente": 0.1, "longueur": 2680,
                 "entraxe": 670, "h_acro": 120}

    # print(charge_neige("A2", 180, GEOMTEST3))

    print(charge_vent("2", "IIIb", GEOMTEST3))
