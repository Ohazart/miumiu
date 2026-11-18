"""Génération du classeur Excel (avec formules vivantes) pour la méthode
Méry-Heyman, et export d'un module VBA (.bas) reproduisant le même calcul.
"""

from __future__ import annotations

import math

import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

import mery_heyman as mh


def _style_header(cell):
    cell.font = Font(bold=True, color="FFFFFF")
    cell.fill = PatternFill("solid", fgColor="305496")
    cell.alignment = Alignment(horizontal="center", vertical="center")


def _style_title(cell):
    cell.font = Font(bold=True, size=13, color="1F3864")


def generer(res_cle, res_crit, AF, P_rupt, lam, pos, sections):
    wb = openpyxl.Workbook()

    # --- Feuille 1 : Paramètres ---
    ws = wb.active
    ws.title = "Parametres"
    ws["A1"] = "MÉTHODE DE MÉRY-HEYMAN - ÉVALUATION DE VÔUTE EN MACONNERIE"
    _style_title(ws["A1"])
    ws["A2"] = "Outil de contrôle d'ingénieur (non réglementaire) - inspiration LimitState:RING"
    ws["A2"].font = Font(italic=True, color="808080")

    rows = [
        ("Portée L (m)", mh.PORTANCE_L),
        ("Flèche f (m)", mh.FLECHE_F),
        ("Largeur participante B (m)", mh.LARGEUR_B),
        ("Épaisseur clé (m)", 0.50),
        ("Épaisseur rein 45° (m)", 1.20),
        ("Épaisseur naissance (m)", 2.86),
        ("Gamma brique (kN/m³)", mh.GAMMA_BRIQUE),
        ("Gamma meulière (kN/m³)", mh.GAMMA_MEULIERE),
        ("Gamma remblai/chaussée (kN/m³)", mh.GAMMA_REMBLAI),
        ("Épaisseur chaussée (m)", mh.EPA_CHAUSSEE),
        ("Charge véhicule service (kN)", mh.CHARGE_VEHICULE),
        ("Nombre de divisions", mh.N_DIV),
        ("Angle élémentaire dθ (°)", 180.0 / mh.N_DIV),
    ]
    r0 = 4
    for k, (label, val) in enumerate(rows):
        ws.cell(row=r0 + k, column=1, value=label).font = Font(bold=True)
        ws.cell(row=r0 + k, column=2, value=val).number_format = "0.000"
    # Cellules nommées pour réutilisation dans les formules
    noms = {
        "B4": "L_portee", "B5": "f_fleche", "B6": "B_largeur",
        "B7": "t_cle", "B8": "t_rein", "B9": "t_naissance",
        "B10": "gamma_brique", "B11": "gamma_meuliere",
        "B12": "gamma_remblai", "B13": "e_chaussee",
        "B14": "P_vehicule", "B15": "N_div", "B16": "dtheta",
    }
    for ref, nom in noms.items():
        wb.defined_names[nom] = openpyxl.workbook.defined_name.DefinedName(
            nom, attr_text=f"Parametres!${ref[0]}${ref[1:]}")

    ws["B18"] = "Position camion (°)"
    ws["B18"].font = Font(bold=True)
    ws["C18"] = 90.0
    ws["C18"].number_format = "0.0"
    wb.defined_names["theta_camion"] = openpyxl.workbook.defined_name.DefinedName(
        "theta_camion", attr_text="Parametres!$C$18")

    ws["B19"] = "Multiplicateur de charge λ"
    ws["B19"].font = Font(bold=True)
    ws["C19"] = 1.0
    ws["C19"].number_format = "0.00"
    wb.defined_names["lam_mult"] = openpyxl.workbook.defined_name.DefinedName(
        "lam_mult", attr_text="Parametres!$C$19")

    # Largeurs
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 14
    ws.column_dimensions["C"].width = 12

    # --- Feuille 2 : Calcul (tableau avec formules vivantes) ---
    wc = wb.create_sheet("Calcul")
    wc["A1"] = "Calcul de la ligne de poussée - Méthode Méry-Heyman"
    _style_title(wc["A1"])
    headers = ["i", "θ (°)", "θ (rad)", "x (m)", "y (m)", "t (m)",
               "ds (m)", "W voûte (kN)", "W remblai (kN)", "W total (kN)",
               "V cumul (kN)", "M (kN.m)", "N (kN)", "e (m)",
               "t/6 (m)", "t/2 (m)", "État Méry", "État Heyman"]
    hr = 3
    for j, h in enumerate(headers, start=1):
        c = wc.cell(row=hr, column=j, value=h)
        _style_header(c)
    wc.row_dimensions[hr].height = 28

    n = len(sections)
    first = hr + 1
    last = hr + n
    dtheta = 180.0 / mh.N_DIV

    # H est une cellule ajustable (équivalent Solver)
    wc.cell(row=1, column=20, value="Poussée H (kN)")
    wc.cell(row=1, column=20).font = Font(bold=True)
    wc.cell(row=1, column=21, value=res_cle.H)
    wc.cell(row=1, column=21).number_format = "0.0"
    wb.defined_names["H_poussee"] = openpyxl.workbook.defined_name.DefinedName(
        "H_poussee", attr_text=f"Calcul!$U$1")

    for k, s in enumerate(sections):
        r = first + k
        # i
        wc.cell(row=r, column=1, value=k)
        # theta (°)
        wc.cell(row=r, column=2, value=f"=B{r-1}+$dtheta" if k > 0 else 0.0)
        if k == 0:
            wc.cell(row=r, column=2, value=0.0)
        # theta (rad)
        wc.cell(row=r, column=3, value=f"=B{r}*PI()/180")
        # x, y
        wc.cell(row=r, column=4,
                value=f"=($L_portee/2)*COS(C{r})")
        wc.cell(row=r, column=5,
                value=f"=($L_portee/2)*SIN(C{r})")
        # t : épaisseur variable interpolée (valeur calculée par Python)
        wc.cell(row=r, column=6, value=s.t)
        # ds
        wc.cell(row=r, column=7,
                value=f"=($L_portee/2)*($dtheta*PI()/180)")
        # W voûte
        wc.cell(row=r, column=8,
                value=f"=F{r}*$B_largeur*G{r}*"
                     f"($gamma_brique*(1-ABS(B{r})/180)+$gamma_meuliere*ABS(B{r})/180)")
        # W remblai
        wc.cell(row=r, column=9,
                value=f"=MAX(0,$f_fleche-E{r})*$B_largeur*G{r}*$gamma_remblai"
                     f"+$e_chaussee*$B_largeur*G{r}*$gamma_remblai")
        # W total
        wc.cell(row=r, column=10, value=f"=H{r}+I{r}")
        # V cumul
        wc.cell(row=r, column=11,
                value=f"=SUM($J${first}:J{r})")
        # M : moment = H*y - somme des W*(x_j - x_i) pour j>i
        # formule matricielle simplifiée via SOMMEPROD
        wc.cell(row=r, column=12,
                value=f"=$H_poussee*E{r}-SUMPRODUCT(($J${first}:$J${last})*"
                     f"($D${first}:$D${last}-D{r})*($D${first}:$D${last}>=D{r}))")
        # Charge camion ajoutée sur la section la plus proche de theta_camion
        # (on l'ajoute dans une colonne auxiliaire)
        # N
        wc.cell(row=r, column=14, value=f"=SQRT($H_poussee^2+K{r}^2)")
        # e
        wc.cell(row=r, column=15, value=f"=IF(N{r}=0,0,L{r}/N{r})")
        # t/6, t/2
        wc.cell(row=r, column=16, value=f"=F{r}/6")
        wc.cell(row=r, column=17, value=f"=F{r}/2")
        # État Méry
        wc.cell(row=r, column=18,
                value=f'=IF(ABS(O{r})<=P{r},"OK","CHARNIERE")')
        # État Heyman
        wc.cell(row=r, column=19,
                value=f'=IF(O{r}>=Q{r},"ART_EXT",IF(O{r}<=-Q{r},"ART_INT","OK"))')

    # Colonne auxiliaire : charge camion (ajoutée à W total)
    wc.cell(row=2, column=23, value="Charge camion sur section (kN)")
    for k, s in enumerate(sections):
        r = first + k
        wc.cell(row=r, column=23,
                value=f"=IF(ABS(B{r}-$theta_camion)<($dtheta/2),"
                     f"$P_vehicule*$lam_mult,0)")
    # Ajouter la charge camion dans W total (colonne J = H+I + charge camion)
    # On remplace la formule de J pour inclure W
    for k, s in enumerate(sections):
        r = first + k
        wc.cell(row=r, column=10,
                value=f"=H{r}+I{r}+W{r}")

    # Synthèse
    sr = last + 2
    wc.cell(row=sr, column=1, value="SYNTHÈSE").font = Font(bold=True, size=12)
    wc.cell(row=sr + 1, column=1, value="Poids total (kN)")
    wc.cell(row=sr + 1, column=2, value=f"=SUM(J{first}:J{last})")
    wc.cell(row=sr + 2, column=1, value="e_max (m)")
    wc.cell(row=sr + 2, column=2,
            value=f"=MAX(ABS(O{first}:O{last}))")
    wc.cell(row=sr + 3, column=1, value="t_min/6 (m)")
    wc.cell(row=sr + 3, column=2,
            value=f"=MIN(F{first}:F{last})/6")
    wc.cell(row=sr + 4, column=1, value="FS (Méry)")
    wc.cell(row=sr + 4, column=2, value=f"=B{sr+3}/B{sr+2}")
    wc.cell(row=sr + 5, column=1, value="Nb articulations Heyman")
    wc.cell(row=sr + 5, column=2,
            value=f'=COUNTIF(S{first}:S{last},"ART_INT")+COUNTIF(S{first}:S{last},"ART_EXT")')

    # Largeurs colonnes
    for col in range(1, 20):
        wc.column_dimensions[get_column_letter(col)].width = 13
    wc.column_dimensions["A"].width = 5

    # --- Feuille 3 : Résultats ---
    wr = wb.create_sheet("Resultats")
    wr["A1"] = "RÉSULTATS - MÉTHODE MÉRY-HEYMAN"
    _style_title(wr["A1"])
    lignes = [
        ("Poussée horizontale H (kN)", res_cle.H),
        ("Poids propre + remblai total (kN)", res_cle.poids_total),
        ("Excentricité maximale e_max (m)", res_cle.e_max),
        ("t_min/6 (m)", res_cle.t_min_sur_6),
        ("FS (Méry, tiers central)", res_cle.FS_mery),
        ("  -> Interprétation", res_cle.fs_interpretation),
        ("Articulations Heyman (hors épaisseur)", res_cle.nb_articulations_heyman),
        ("Position critique du camion (°)", res_crit.position_critique_deg),
        ("Multiplicateur de rupture λ", lam),
        ("Charge de rupture (kN)", P_rupt),
        ("Adequacy Factor AF", AF),
        ("  -> Interprétation AF",
         "Ruine" if AF < 1 else "Limite" if AF < 1.5 else "Acceptable"
         if AF < 2 else "Bon" if AF < 3 else "Très robuste"),
    ]
    for k, (lab, val) in enumerate(lignes):
        wr.cell(row=3 + k, column=1, value=lab).font = Font(bold=True)
        c = wr.cell(row=3 + k, column=2, value=val)
        if isinstance(val, float):
            c.number_format = "0.00"
    wr["A17"] = "Critères"
    wr["A17"].font = Font(bold=True, size=11)
    wr["A18"] = "Méry   : |e| <= t/6 (tiers central, pas de traction)"
    wr["A19"] = "Heyman : |e| <= t/2 (ligne dans l'épaisseur)"
    wr["A20"] = "RING   : 4 articulations -> mécanisme -> ruine"
    wr.column_dimensions["A"].width = 40
    wr.column_dimensions["B"].width = 16

    wb.save("voute_mery_heyman.xlsx")


# ---------------------------------------------------------------------------
# Fonction d'épaisseur pour Excel (UDF VBA ou formule nommée)
# On l'écrit aussi comme macro VBA dans le module .bas
# ---------------------------------------------------------------------------

def generer_vba():
    """Génère un module VBA (.bas) reproduisant le calcul complet."""
    code = r'''Attribute VB_Name = "MeryHeyman"
Option Explicit

'==========================================================================
' MÉTHODE DE MÉRY-HEYMAN - ÉVALUATION DE VÔUTE EN MACONNERIE
' Module VBA - contrôle d'ingénieur (non réglementaire)
' Inspiration LimitState:RING / théorie de Heyman (1960)
'==========================================================================

' --- Paramètres par défaut (modifiables) ---
Public Const LPORTEE As Double = 11#     ' portée (m)
Public Const FFLECHE As Double = 5.5     ' flèche (m)
Public Const BLARGEUR As Double = 3.8    ' largeur participante (m)
Public Const GAMMABRIQUE As Double = 18#  ' kN/m3
Public Const GAMMAMEULIERE As Double = 22# ' kN/m3
Public Const GAMMAREMBLAI As Double = 21# ' kN/m3
Public Const ECHAUSSEE As Double = 0.4    ' m
Public Const PVEHICULE As Double = 120#   ' kN (camion 12 t)
Public Const NDIV As Integer = 36         ' secteurs de 5°

'-----------------------------------------------------------------
' Épaisseur variable (interpolation linéaire sur angle absolu 0..90)
' Points de calage : naissance 2.86, rein 1.20, clé 0.50
'-----------------------------------------------------------------
Public Function EpaisseurVoute(thetaDeg As Double) As Double
    Dim a As Double
    a = Abs(thetaDeg)
    If a > 90 Then a = 180# - a
    ' interpolation linéaire par morceaux
    Dim ang(0 To 6) As Double, ep(0 To 6) As Double
    ang(0) = 0#: ep(0) = 2.86
    ang(1) = 15#: ep(1) = 2.3
    ang(2) = 30#: ep(2) = 1.8
    ang(3) = 45#: ep(3) = 1.2
    ang(4) = 60#: ep(4) = 0.9
    ang(5) = 75#: ep(5) = 0.65
    ang(6) = 90#: ep(6) = 0.5
    Dim j As Integer
    If a <= ang(0) Then EpaisseurVoute = ep(0): Exit Function
    If a >= ang(6) Then EpaisseurVoute = ep(6): Exit Function
    For j = 0 To 5
        If a >= ang(j) And a <= ang(j + 1) Then
            EpaisseurVoute = ep(j) + (ep(j + 1) - ep(j)) * (a - ang(j)) / (ang(j + 1) - ang(j))
            Exit Function
        End If
    Next j
    EpaisseurVoute = ep(6)
End Function

'-----------------------------------------------------------------
' Gamma moyen pondéré brique/meulière
'-----------------------------------------------------------------
Public Function GammaMoyen(thetaDeg As Double) As Double
    Dim a As Double
    a = Abs(thetaDeg)
    If a > 90 Then a = 180# - a
    Dim frac As Double
    frac = a / 90#
    GammaMoyen = GAMMABRIQUE * (1# - frac) + GAMMAMEULIERE * frac
End Function

'-----------------------------------------------------------------
' Calcul de la ligne de poussée pour une position de camion
' H est optimisé pour minimiser l'excentricité normalisée max(|e|/(t/2))
'-----------------------------------------------------------------
Public Sub CalculerLignePoussee(thetaCamion As Double, charge As Double, _
                                ByRef H As Double, ByRef eMax As Double, _
                                ByRef nbArt As Integer)
    Dim R As Double, dtheta As Double, ds As Double
    R = LPORTEE / 2#
    dtheta = 180# / NDIV
    ds = R * (dtheta * 3.14159265358979 / 180#)
    
    Dim i As Integer, n As Integer
    n = NDIV + 1
    Dim theta(0 To 100) As Double, x(0 To 100) As Double, y(0 To 100) As Double
    Dim t(0 To 100) As Double, W(0 To 100) As Double
    Dim e(0 To 100) As Double, t2(0 To 100) As Double
    
    For i = 0 To n - 1
        theta(i) = i * dtheta
        x(i) = R * Cos(theta(i) * 3.14159265358979 / 180#)
        y(i) = R * Sin(theta(i) * 3.14159265358979 / 180#)
        t(i) = EpaisseurVoute(theta(i))
        Dim hremblai As Double
        hremblai = Application.WorksheetFunction.Max(0, FFLECHE - y(i)) + ECHAUSSEE
        W(i) = t(i) * BLARGEUR * ds * GammaMoyen(theta(i)) _
             + hremblai * BLARGEUR * ds * GAMMAREMBLAI
    Next i
    ' Charge camion sur section la plus proche
    Dim idxC As Integer
    idxC = CInt(thetaCamion / dtheta)
    If idxC < 0 Then idxC = 0
    If idxC > n - 1 Then idxC = n - 1
    W(idxC) = W(idxC) + charge
    
    ' Estimation initiale H0
    Dim Q As Double, H0 As Double
    Q = 0
    For i = 0 To n - 1
        Q = Q + W(i)
    Next i
    H0 = Q * LPORTEE ^ 2 / (8# * FFLECHE)
    
    ' Optimisation H par balayage (recherche grossière puis fine)
    Dim Hbest As Double, costBest As Double
    Hbest = H0
    costBest = 1E+30
    Dim Htest As Double, cost As Double
    Dim k As Long
    For k = 0 To 400
        Htest = H0 * 0.2 + (H0 * 4# - H0 * 0.2) * k / 400
        cost = CoutH(Htest, n, x, y, W, t, e, t2)
        If cost < costBest Then
            costBest = cost
            Hbest = Htest
        End If
    Next k
    ' Affinage
    Dim Hlo As Double, Hhi As Double
    Hlo = Hbest * 0.95
    Hhi = Hbest * 1.05
    For k = 0 To 400
        Htest = Hlo + (Hhi - Hlo) * k / 400
        cost = CoutH(Htest, n, x, y, W, t, e, t2)
        If cost < costBest Then
            costBest = cost
            Hbest = Htest
        End If
    Next k
    
    ' Recalcul final
    Call CoutH(Hbest, n, x, y, W, t, e, t2)
    H = Hbest
    eMax = 0
    nbArt = 0
    For i = 0 To n - 1
        If Abs(e(i)) > eMax Then eMax = Abs(e(i))
        If e(i) >= t2(i) Or e(i) <= -t2(i) Then nbArt = nbArt + 1
    Next i
End Sub

' Fonction coût : max(|e|/(t/2))
Private Function CoutH(H As Double, n As Integer, _
                       x As Double, y As Double, W As Double, _
                       t As Double, ByRef e As Double, ByRef t2 As Double) As Double
    Dim i As Integer, j As Integer
    Dim Vcum As Double, M As Double, N As Double
    Dim eabs As Double, emax As Double
    emax = 0
    For i = 0 To n - 1
        Vcum = 0
        M = H * y(i)
        For j = i + 1 To n - 1
            Vcum = Vcum + W(j)
            M = M - W(j) * (x(j) - x(i))
        Next j
        Vcum = Vcum + W(i)
        N = Sqr(H ^ 2 + Vcum ^ 2)
        If N = 0 Then
            e(i) = 0
        Else
            e(i) = M / N
        End If
        t2(i) = t(i) / 2
        eabs = Abs(e(i)) / t2(i)
        If eabs > emax Then emax = eabs
    Next i
    CoutH = emax
End Function

'-----------------------------------------------------------------
' Recherche de la position critique du camion
'-----------------------------------------------------------------
Public Sub RecherchePositionCritique(charge As Double, _
                                     ByRef thetaCrit As Double, _
                                     ByRef eMaxCrit As Double)
    Dim k As Integer, theta As Double
    Dim H As Double, eMax As Double, nbArt As Integer
    thetaCrit = 0
    eMaxCrit = 0
    For k = 0 To NDIV
        theta = k * (180# / NDIV)
        Call CalculerLignePoussee(theta, charge, H, eMax, nbArt)
        If eMax > eMaxCrit Then
            eMaxCrit = eMax
            thetaCrit = theta
        End If
    Next k
End Sub

'-----------------------------------------------------------------
' Calcul de l'Adequacy Factor (mécanisme 4 articulations)
'-----------------------------------------------------------------
Public Function AdequacyFactor() As Double
    Dim lamLo As Double, lamHi As Double, lamMid As Double
    Dim charge As Double
    Dim theta As Double, eMax As Double, H As Double, nbArt As Integer
    lamLo = 1#
    Call RecherchePositionCritique(lamLo * PVEHICULE, theta, eMax)
    Call CalculerLignePoussee(theta, lamLo * PVEHICULE, H, eMax, nbArt)
    If nbArt >= 4 Then
        AdequacyFactor = 1#
        Exit Function
    End If
    lamHi = 1#
    Do
        lamHi = lamHi * 1.5
        Call RecherchePositionCritique(lamHi * PVEHICULE, theta, eMax)
        Call CalculerLignePoussee(theta, lamHi * PVEHICULE, H, eMax, nbArt)
        If nbArt >= 4 Then Exit Do
    Loop Until lamHi > 100000
    ' Dichotomie
    Dim k As Integer
    For k = 1 To 80
        lamMid = (lamLo + lamHi) / 2
        Call RecherchePositionCritique(lamMid * PVEHICULE, theta, eMax)
        Call CalculerLignePoussee(theta, lamMid * PVEHICULE, H, eMax, nbArt)
        If nbArt >= 4 Then
            lamHi = lamMid
        Else
            lamLo = lamMid
        End If
        If lamHi - lamLo < 0.001 Then Exit For
    Next k
    AdequacyFactor = lamHi
End Function

'-----------------------------------------------------------------
' Procédure principale : exécuter dans Excel (Alt-F8 -> RunMeryHeyman)
'-----------------------------------------------------------------
Public Sub RunMeryHeyman()
    Dim ws As Worksheet
    On Error Resume Next
    Set ws = ThisWorkbook.Worksheets("Resultats_VBA")
    If ws Is Nothing Then
        Set ws = ThisWorkbook.Worksheets.Add(After:=ThisWorkbook.Sheets(ThisWorkbook.Sheets.Count))
        ws.Name = "Resultats_VBA"
    End If
    On Error GoTo 0
    ws.Cells.Clear
    ws.Range("A1") = "MÉTHODE DE MÉRY-HEYMAN - RÉSULTATS VBA"
    ws.Range("A1").Font.Bold = True
    
    Dim H As Double, eMax As Double, nbArt As Integer
    Dim thetaCrit As Double, eMaxCrit As Double
    Dim AF As Double
    
    Call CalculerLignePoussee(90#, PVEHICULE, H, eMax, nbArt)
    Call RecherchePositionCritique(PVEHICULE, thetaCrit, eMaxCrit)
    AF = AdequacyFactor()
    
    Dim tMin As Double
    tMin = 0.5  ' épaisseur à la clé
    
    ws.Range("A3") = "Poussée H (kN)": ws.Range("B3") = H
    ws.Range("A4") = "e_max (m)": ws.Range("B4") = eMax
    ws.Range("A5") = "t_min/6 (m)": ws.Range("B5") = tMin / 6
    ws.Range("A6") = "FS (Méry)": ws.Range("B6") = (tMin / 6) / eMax
    ws.Range("A7") = "Articulations (Heyman)": ws.Range("B7") = nbArt
    ws.Range("A8") = "Position critique (°)": ws.Range("B8") = thetaCrit
    ws.Range("A9") = "Adequacy Factor AF": ws.Range("B9") = AF
    
    ws.Range("A11") = "Critères:"
    ws.Range("A12") = "Méry : |e| <= t/6"
    ws.Range("A13") = "Heyman : |e| <= t/2"
    ws.Range("A14") = "RING : 4 articulations -> ruine"
    
    MsgBox "Calcul terminé. AF = " & Format(AF, "0.00") & vbCrLf & _
           "FS (Méry) = " & Format((tMin / 6) / eMax, "0.00"), _
           vbInformation, "Méry-Heyman"
End Sub
'''
    with open("MeryHeyman.bas", "w", encoding="utf-8") as f:
        f.write(code)


if __name__ == "__main__":
    generer_vba()
    print("Module VBA MeryHeyman.bas généré.")
