# Sample Data

Place PSV files from the [PhysioNet/CinC 2019 Challenge](https://physionet.org/content/challenge-2019/1.0.0/) here.

```bash
# Example: copy the first 10 patients from training set A
cp /path/to/training_setA/p00000*.psv data/sample/
```

The CDA preprocessing service will read every `*.psv` file in this directory.

> **Note:** Do not commit real patient data to the repository.
