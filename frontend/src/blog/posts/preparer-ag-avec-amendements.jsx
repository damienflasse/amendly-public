export default function Post() {
  return (
    <>
      <p>
        Une assemblée générale avec un ordre du jour chargé d'amendements, ça se prépare
        bien en amont. Pourtant, dans la plupart des associations et syndicats, la préparation
        ressemble encore à ceci : un document Word envoyé par email, une boîte de réception
        saturée de propositions contradictoires, et un bureau qui passe la nuit précédant
        l'AG à tout compiler à la main.
      </p>
      <p>
        Ce guide décrit une méthode structurée en quatre étapes, applicable quel que soit
        l'outil utilisé — et optimisée si vous passez à une plateforme dédiée.
      </p>

      <hr />

      <h2>Étape 1 — Définir le cadre avant d'ouvrir les propositions</h2>
      <p>
        Avant que les membres ne commencent à soumettre des amendements, trois règles
        doivent être posées clairement :
      </p>
      <p>
        <strong>Qui peut proposer un amendement ?</strong> Tous les adhérents ? Uniquement
        les membres à jour de cotisation ? Les délégués mandatés ? Le flou ici génère des
        conflits de procédure le jour J.
      </p>
      <p>
        <strong>Sur quel texte porte l'amendement ?</strong> Il faut publier la version
        officielle du texte soumis à l'AG — statuts, règlement intérieur, résolution —
        et geler ce document de référence. Tout amendement doit citer l'article exact qu'il
        modifie.
      </p>
      <p>
        <strong>Jusqu'à quand peut-on déposer ?</strong> Une date limite claire est
        indispensable. Sans elle, des amendements continuent d'arriver jusqu'à la veille,
        rendant toute consolidation impossible.
      </p>

      <hr />

      <h2>Étape 2 — Collecter les amendements de façon structurée</h2>
      <p>
        C'est là que la plupart des organisations perdent du temps. Quand chaque membre
        envoie sa proposition dans un format différent — un tableau Excel, un email en prose,
        un PDF scanné — la consolidation prend des heures.
      </p>
      <p>
        La solution : imposer un formulaire de dépôt unique qui recueille systématiquement :
      </p>
      <p>
        — la référence de l'article concerné<br />
        — le texte actuel (extrait exact)<br />
        — le texte proposé<br />
        — la justification (facultative mais utile pour le débat)
      </p>
      <p>
        Avec un outil comme Amendly, ce formulaire est intégré : le membre sélectionne
        le passage à modifier directement dans le document, propose son remplacement, et
        le diff est calculé automatiquement. Plus de copier-coller, plus d'erreurs de
        référencement.
      </p>

      <hr />

      <h2>Étape 3 — Organiser la revue avant l'AG</h2>
      <p>
        Une fois la période de dépôt fermée, le travail de revue commence. Il y a généralement
        deux niveaux :
      </p>
      <p>
        <strong>La recevabilité :</strong> l'amendement respecte-t-il les règles formelles
        (délai, format, périmètre) ? C'est un contrôle rapide mais indispensable. Les
        amendements irrecevables doivent être notifiés à leurs auteurs avant l'AG.
      </p>
      <p>
        <strong>La préparation du débat :</strong> pour les amendements recevables, le bureau
        peut préparer une position (favorable / défavorable / renvoi en commission) et
        regrouper les amendements portant sur le même article. Cela évite de débattre
        vingt fois du même paragraphe.
      </p>
      <p>
        Dans Amendly, les administrateurs peuvent ajouter des commentaires et des réactions
        sur chaque amendement, et les regrouper par article. Le jour de l'AG, tout le monde
        part du même tableau de bord.
      </p>

      <hr />

      <h2>Étape 4 — Consolider et exporter après le vote</h2>
      <p>
        L'AG vote, les amendements sont acceptés ou rejetés. Vient alors la phase la plus
        fastidieuse : intégrer les amendements acceptés dans le texte final et produire
        un document propre pour signature et archivage.
      </p>
      <p>
        Manuellement, cela consiste à rouvrir le document original et à y copier-coller
        chaque modification votée — avec le risque d'en oublier une, ou d'introduire une
        erreur de numérotation d'article.
      </p>
      <p>
        Avec une plateforme dédiée, la consolidation est quasi-automatique : accepter un
        amendement l'injecte directement dans le texte consolidé. À la fin, un clic suffit
        pour exporter le document final en DOCX ou PDF, prêt à être signé.
      </p>

      <hr />

      <h2>Ce que change une préparation structurée</h2>
      <p>
        Une AG mal préparée sur les amendements aboutit à trois problèmes récurrents :
        des débats qui s'enlisent sur des questions de forme, des votes sur des textes
        que la salle n'a pas lus, et un bureau épuisé qui repart avec un document à
        reconstituer dans l'urgence.
      </p>
      <p>
        Une préparation structurée déplace le travail : au lieu de courir après les
        informations le jour J, on passe du temps en amont à organiser le cadre. L'AG
        devient alors ce qu'elle devrait être — un moment de décision, pas de saisie.
      </p>
      <p>
        <em>
          Amendly est conçu pour exactement cette situation : collecter les amendements
          de façon structurée, les réviser en équipe, les consolider en un clic.{' '}
          <a href="https://amendly.eu" className="text-amendly-blue hover:underline font-medium">
            Essayez gratuitement
          </a>{' '}
          avant votre prochaine assemblée générale.
        </em>
      </p>
    </>
  )
}
