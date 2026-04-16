; demo.nc - Fichier G-code de démonstration SENTINELLE CNC
; Carré 100x100mm avec passe de finition circulaire au centre
; Généré pour tests du simulateur visuel

G21          ; Unités en millimètres
G90          ; Positionnement absolu
G17          ; Plan XY

; Départ origine
G01 X0 Y0 F500

; Contour carré 100x100mm (sens horaire)
G01 X100 Y0 F800    ; Droite
G01 X100 Y100       ; Haut
G01 X0 Y100         ; Gauche
G01 X0 Y0           ; Bas (retour origine)

; Passe de finition circulaire au centre (rayon 25mm)
; Centre du cercle : X50 Y50
G01 X75 Y50 F600    ; Position départ cercle (droite du centre)
G02 X75 Y50 I-25 J0 ; Cercle complet (sens horaire)

; Retour origine
G01 X0 Y0 F800

M30          ; Fin du programme
