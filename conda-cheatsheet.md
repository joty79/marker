# Conda Cheatsheet

## Εγκατάσταση και Ρύθμιση

| Εντολή | Περιγραφή |
|--------|-----------|
| `conda --version` | Εμφάνιση της έκδοσης conda |
| `conda update conda` | Ενημέρωση του conda στην τελευταία έκδοση |
| `conda config --show` | Εμφάνιση των ρυθμίσεων conda |
| `conda config --set auto_activate_base false` | Απενεργοποίηση αυτόματης ενεργοποίησης του base environment |
| `conda info` | Εμφάνιση πληροφοριών για το conda installation |

## Διαχείριση Environment

| Εντολή | Περιγραφή |
|--------|-----------|
| `conda create -n myenv python=3.9` | Δημιουργία νέου environment με συγκεκριμένη έκδοση Python |
| `conda activate myenv` | Ενεργοποίηση environment |
| `conda deactivate` | Απενεργοποίηση τρέχοντος environment |
| `conda env list` | Εμφάνιση όλων των environment |
| `conda env remove -n myenv` | Διαγραφή environment |
| `conda env export > environment.yml` | Εξαγωγή environment σε αρχείο YAML |
| `conda env create -f environment.yml` | Δημιουργία environment από αρχείο YAML |
| `conda env update -f environment.yml` | Ενημέρωση environment από αρχείο YAML |

## Διαχείριση Packages

| Εντολή | Περιγραφή |
|--------|-----------|
| `conda install package_name` | Εγκατάσταση package |
| `conda install package_name=1.0.0` | Εγκατάσταση συγκεκριμένης έκδοσης package |
| `conda install package1 package2` | Εγκατάσταση πολλαπλών packages |
| `conda uninstall package_name` | Απεγκατάσταση package |
| `conda list` | Εμφάνιση όλων των εγκατεστημένων packages στο τρέχον environment |
| `conda search package_name` | Αναζήτηση διαθέσιμων εκδόσεων ενός package |
| `conda update package_name` | Ενημέρωση package στην τελευταία έκδοση |
| `conda update --all` | Ενημέρωση όλων των packages |

## Channels

| Εντολή | Περιγραφή |
|--------|-----------|
| `conda config --add channels channel_name` | Προσθήκη channel για εγκατάσταση packages |
| `conda config --remove channels channel_name` | Αφαίρεση channel |
| `conda install -c channel_name package_name` | Εγκατάσταση package από συγκεκριμένο channel |
| `conda config --set channel_priority strict` | Ορισμός αυστηρής προτεραιότητας καναλιών |

## Χρήσιμα Tips

- Χρησιμοποιήστε `conda clean --all` για καθαρισμό προσωρινών αρχείων και μη χρησιμοποιούμενων packages
- Προτιμήστε τη δημιουργία ξεχωριστού environment για κάθε project
- Χρησιμοποιήστε το `mamba` ως εναλλακτικό, πιο γρήγορο frontend για το conda
- Συνδυάστε το conda με το pip εγκαθιστώντας πρώτα dependencies με το conda και στη συνέχεια χρησιμοποιώντας το pip για τα υπόλοιπα

## Αντιμετώπιση Προβλημάτων

| Εντολή | Περιγραφή |
|--------|-----------|
| `conda clean --all` | Καθαρισμός της conda cache |
| `conda config --set channel_priority flexible` | Ορισμός ευέλικτης προτεραιότητας καναλιών για επίλυση συγκρούσεων |
| `conda install --revision=0` | Επαναφορά του environment στην αρχική κατάσταση |
| `conda list --revisions` | Εμφάνιση ιστορικού αλλαγών στο environment |