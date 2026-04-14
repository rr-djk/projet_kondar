# TODOS — SENTINELLE CNC

## [ACOUSTIC] Bouton explicite "Démarrer baseline"

**Quoi :** Ajouter un bouton dans l'UI pygame qui lance la capture de baseline acoustique sur demande, plutôt qu'automatiquement au démarrage.

**Pourquoi :** Si la machine tourne déjà en conditions anormales au lancement, la baseline est corrompue. Tous les seuils de détection sont alors faux pour toute la session — faux négatifs silencieux.

**Pros :** Fix le gap critique identifié en architecture review. Opérateur contrôle quand la baseline est capturée (après s'être assuré que la coupe est normale).

**Cons :** Ajoute une étape manuelle au setup. L'opérateur doit penser à appuyer.

**Contexte :** Dans `acoustic/analyzer.py`, la fonction `compute_baseline()` est déjà une fonction pure. Il suffit de l'appeler sur clic bouton plutôt qu'au démarrage. Dans `visual/simulator.py`, ajouter un bouton pygame "BASELINE" et un état `baseline_ready: bool`. Tant que `baseline_ready=False`, afficher "EN ATTENTE BASELINE" et désactiver les alertes.

**Dépend de :** `acoustic/analyzer.py` et `visual/simulator.py` implémentés.

---

## [VISUAL] Afficher "ACOUSTIC OFFLINE" si WebSocket non connecté

**Quoi :** Si le Pi n'est pas joignable au démarrage du laptop, afficher un indicateur visible dans l'UI plutôt que silence.

**Pourquoi :** Sans ça, l'opérateur peut lancer la démo en pensant que le pilier acoustique tourne, alors qu'il est hors ligne. Gap critique identifié en review.

**Pros :** Feedback immédiat. Évite les faux sentiments de sécurité en démo.

**Cons :** Trivial à implémenter (check connection state dans la queue consumer).

**Contexte :** Dans `visual/simulator.py`, le thread WebSocket daemon envoie un event `{"type": "status", "connected": false}` si la connexion échoue après 5s. La boucle pygame affiche un badge rouge "ACOUSTIC OFFLINE" dans le coin de l'UI.

**Dépend de :** IPC WebSocket intégration (Lane C).
