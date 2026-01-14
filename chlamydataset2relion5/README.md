# chlamydataset2relion5
Python script to import pre-processed results from the Chlamy dataset ([EMPIAR-11830](https://www.ebi.ac.uk/empiar/EMPIAR-11830/)) into [Relion-5](https://relion.readthedocs.io/en/release-5.0/STA_tutorial/index.html). The script takes care of appropriately parsing the several deposited MRC and associated metadata files into one `.star` file per tilt-series, which in turn are referenced by a `tomograms.star` file. These are the files that can be used for subtomogram averaging in Relion-5.

# Dependencies
The script was tested with the following environment:
* [python](https://www.python.org/)==3.12.2
* [numpy](https://numpy.org/)==1.26.4
* [starfile](https://github.com/teamtomo/starfile)==0.5.6

## Creating an environment:

You can create a minimal conda environment to run the script:

```bash
conda create -n chlamy2relion python=3.12 -y
conda activate chlamy2relion
pip install numpy starfile
```

# Usage instructions

1. Clone this repo:
   
```bash
git clone git@github.com:Chromatin-Structure-Rhythms-Lab/ChlamyAnnotations.git
```
   
2. Download the desired tomogram folders contained in the [chlamy_visual_proteomics](https://ftp.ebi.ac.uk/empiar/world_availability/11830/data/chlamy_visual_proteomics/) directory from [EMPIAR-11830](https://www.ebi.ac.uk/empiar/EMPIAR-11830/). Example for downloading tilt-series `01082023_BrnoKrios_Arctis_WebUI_Position_8`:

```bash
mkdir EMPIAR-11830
cd EMPIAR-11830

wget -r -N -np -nH --cut-dirs=4 --reject "*.eer,*.rawtlt,*_dose-filt.st,*_EVN.st,*_ODD.st" ftp://ftp.ebi.ac.uk/empiar/world_availability/11830/data/chlamy_visual_proteomics/01082023_BrnoKrios_Arctis_WebUI_Position_8/
```

**NOTE:** in the `wget` command above we intentionally exclude large files which are not essential for subtomogram averaging in RELION-5. Adjust accordingly depending on which files you want to download. 

3. **OPTIONAL:** Download the [ctf3d](https://ftp.ebi.ac.uk/empiar/world_availability/11830/data/ctf3d_bin4/) and [cryo-CARE](https://ftp.ebi.ac.uk/empiar/world_availability/11830/data/cryocare_bin4/) denoised tomograms (see example above)

* The `cryocare_bin4` tomograms have higher contrast, they are good for visualization and deep learning-based particle pickers
* The `ctf3d_bin4` tomograms have high-resolution information preserved (despite lower contrast) and are good for template matching

4. Run the script:

```bash
cd ChlamyAnnotations/chlamydataset2relion5/

python chlamydataset2relion5.py --tomos_dir /path/to/chlamy_visual_proteomics/ --output_dir /path/to/relion5/project/ --correspondence_star tomolist_num_dir.star --ctf3d /path/to/bin4_ctf3d/ --cryocare /path/to/bin4_cryocare/
```

**Tip:** the `tomolist_num_dir.star` file is provided in this repo for convenience. Alternatively, it can also be [downloaded](https://ftp.ebi.ac.uk/empiar/world_availability/11830/data/chlamy_visual_proteomics/tomolist_num_dir.star) from EMPIAR.

**A note on paths:** \
Please note that the paths provided with the `--ctf3d` and `--cryocare` options don't need to exist. They will just be written in the resulting `tomograms.star` file referencing the corresponding CTF-corrected and denoised tomograms for each tilt-series, regardless of whether they exist or not in your filesystem.

5. **Profit!** The generated `/path/to/relion5/project/tomograms.star` can be used as a direct entry in Relion-5 jobs.

   **NOTE:** make sure you launch Relion-5 in tomography mode, i.e. by running `relion --tomo &`

6. **OPTIONAL:** for a sanity check, it's a good idea to have Relion reconstruct at least one imported tomogram and make sure it matches the deposited ctf3d or cryo-CARE bin4 tomogram:
![image](https://github.com/user-attachments/assets/a37b6556-b14c-4951-b92a-87bc2094c1b8)

# Acknowledgments
This script is almost entirely derived from [aretomo3torelion5](https://github.com/Phaips/aretomo3torelion5/) from [@Phaips](https://github.com/Phaips) 🚀

# References & See Also

Please see the main repo [README](../README.md) for the project manuscript and additional resources.

