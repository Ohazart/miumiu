Attribute VB_Name = "MeryHeyman"
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
