# 🛡️ Projet : SENTINELLE CNC (Système de Vigilance Active)

## 1. Vision du Projet

**Problématique :** Le "Fossé de Réalité" (Reality Gap). Les programmes CNC sont générés dans un environnement numérique parfait qui ne tient pas compte des imprévus physiques (brides de serrage mal placées, décalages d'origine, usure d'outil).

**Solution :** Un boîtier externe "Plug & Play" utilisant la vision par ordinateur et l'analyse acoustique pour agir comme un copilote intelligent pour l'opérateur.

---

## 2. Analyse du Problème (Le "Pourquoi")

- **Sécurité et Coût :** Un crash d'outil coûte cher (500$+) et immobilise une machine qui peut coûter jusqu'à 500$/heure en perte de productivité.
- **Perte d'Expertise :** L'oreille de l'opérateur "senior" (détection de la charge et de la casse par le son) est une compétence longue à acquérir.
- **Limites de l'existant :** Les simulations logicielles ne voient pas le réel, et les capteurs de charge machine réagissent souvent après le dommage.

---

## 3. Architecture de la Solution (Le "Comment")

Le système repose sur deux piliers d'analyse en temps réel :

### A. Pilier Visuel (Vision par Ordinateur)

- **Objectif :** Détecter les collisions avant qu'elles n'arrivent.
- **Logique :** Comparer le vecteur de déplacement de l'outil (prédiction) avec les obstacles physiques détectés sur la table.
- **Action :** Arrêt d'urgence ou recalcul dynamique d'une trajectoire de contournement (Path Planning).

### B. Pilier Acoustique (Analyse de Signal)

- **Objectif :** Surveiller la santé de la coupe.
- **Logique :** Analyser les fréquences sonores (FFT) pour identifier le "bruit" d'une casse imminente ou d'une surcharge.
- **Action :** Notification à l'opérateur pour ajuster le RPM ou l'avance (Feedrate).

---

## 4. Roadmap de Développement (Les Étapes)

### Phase 1 : Le Noyau Algorithmique (Software-Only)

- **Tâche :** Créer un simulateur 2D/3D sur ordinateur.
- **Entrée :** Un flux vidéo (webcam standard).
- **Défis :**
  - Isoler l'outil (objet mobile) des obstacles (objets statiques).
  - Coder l'algorithme d'évitement (calcul d'un chemin alternatif entre le point A et B).
- **Livrable :** Une démonstration logicielle où un curseur évite un obstacle posé devant la caméra.

### Phase 2 : L'Intelligence Sensorielle (Hardware Edge)

- **Tâche :** Déployer la détection sur un microcontrôleur avec caméra et micro.
- **Défis :**
  - Optimiser le code pour qu'il tourne sur du matériel limité (Edge Computing).
  - Gérer la communication entre le capteur (Caméra) et l'interface (Écran/PC).
- **Livrable :** Un prototype qui déclenche une alerte visuelle/sonore en tenant compte d'un environnement réel.

### Phase 3 : L'Intégration et la Preuve de Concept

- **Tâche :** Créer la maquette physique (mécanique).
- **Défis :**
  - Simuler l'axe d'une machine (moteur pas-à-pas).
  - Concevoir un boîtier (impression 3D) capable de protéger l'électronique des projections (étanchéité).
- **Livrable :** Un système complet capable d'arrêter un mouvement moteur si un obstacle imprévu est détecté.

---

## 5. Proposition de Valeur Business (Le Pitch)

- **Retrofitting :** Modernise les machines anciennes pour une fraction du prix d'une machine neuve.
- **Productivité :** Réduit le temps de "proofing" (première pièce) en sécurisant les déplacements rapides.
- **Formation :** Aide les opérateurs débutants à comprendre les limites de l'outil grâce aux alertes sonores intelligentes.

---

## 6. Défis Techniques à Anticiper

- **Latence :** Le temps entre la détection et l'arrêt doit être inférieur à quelques millisecondes.
- **Environnement :** La lentille doit rester propre (poussière, huile).
- **Fiabilité :** L'algorithme de recalcul ne doit pas générer une collision pire que celle qu'il évite.

---

## Note de collaboration

> Ce document est conçu pour être évolutif. Chaque étape franchie valide une brique technologique indispensable pour la suite du projet.  
> La force de cette approche est qu'elle est "découplée" : on peut améliorer l'IA sans toucher au hardware, et vice versa.
