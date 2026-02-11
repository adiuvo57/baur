# QRCODE_SCAN (Switzerland only)

Le but de ce module est de permettre la génération de facture dans Odoo à partir d'un QR code (uniquement en Suisse et au Liechtenstein).

Il est conçu pour fonctionner avec un QR code scan [comme celui-ci par exemple.](https://www.zebra.com/fr/fr/products/scanners/general-purpose-scanners/handheld/ds2200-series.html)

## Vérification
Le compte fourni par le QR code doit être au format IBAN.
Si le débiteur précisé par le QR code n'existe pas, il sera créer en tant que contact avec l'adrese fournie.
Attention, si le débiteur n'existe pas mais que l'IBAN précisé par le QR code existe, le système va lever une erreur d'utilisation.


## Comment utiliser la fonction "QR code scan" ?
Dans le module "accounting", cliquez sur Achats dans le menu puis QR code.
Un wizard s'ouvre : vous pouvez scanner votre QR code.
Un fois le QR code scanné, vous cliquez sur le bouton "Générer facture".
La facture est alors générée à l'état "brouillon", vous n'avez plus qu'à la comptabiliser et/ou enregistrer un paiement.