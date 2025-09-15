# Particle annotations for *In-cell architecture of the mitochondrial respiratory chain*

We provide here the following particle annotations described in the ([Chlamy respirasome paper](https://doi.org/10.1126/science.ads8738)): respirasome (C2), mitoribosome, ATP synthase, HSP60 and putative prohibitin. Unbinned particle coordinates and orientations are stored in the RELION-3 `.star` file format with the pixel size of 1.96 Å - available in the [star](star) folder.

The annotations of each particle were used to create the subtomogram averages - available in the [densities](densities) folder.

| particle | coordinates | density | density_EMDB | resolution | representative_tomogram | comment |
| -------- | ----------- | ------- | ------------ | ---------- | ----------------------- | ------- |
| respirasome         | [respirasome.star](star/respirasome.star)					| [respirasome.mrc](densities/respirasome.mrc)				   	| [EMD-50210](https://www.ebi.ac.uk/emdb/EMD-50210) | 5.44 Å (here 7.84 Å)| tomo_0054 | This is the version of the map refined with C2 symmetry. We provide here a 2x downsampled map, for the full unbinned map please see the EMDB entry. |
| putative prohibitin         | [putative_prohibitin.star](star/putative_prohibitin.star)					| [putative_prohibitin.mrc](densities/putative_prohibitin.mrc)				   	| [EMD-50212](https://www.ebi.ac.uk/emdb/EMD-50212) | 28.5 Å | tomo_0054 ||
| mitoribosome         | [mitoribosome.star](star/mitoribosome.star)					| [mitoribosome.mrc](densities/mitoribosome.mrc)				   	| [EMD-50213](https://www.ebi.ac.uk/emdb/EMD-50213) | 21.8 Å | tomo_0054 ||
| ATP synthase         | [atpase.star](star/atpase.star)					| [atpase.mrc](densities/atpase.mrc)				   	| N/A | 15.68 Å | tomo_0054 | For visualization purposes, only tomo_0054 was processed (Fig. 1 of the paper). |
| HSP60         | [hsp60.star](star/hsp60.star)					| [hsp60.mrc](densities/hsp60.mrc)				   	| N/A | 15.68 Å | tomo_0054 | For visualization purposes, only tomo_0054 was processed (Fig. 1 of the paper). |

----
## Visualization & manipulation in Python

Please see instructions [here](../10.1101-2024.12.28.630444/README.md) for manipulating the files in Python and visualizing them in [ChimeraX](https://www.cgl.ucsf.edu/chimerax/) / [ArtiaX](https://github.com/FrangakisLab/ArtiaX).

## Publication

Waltz, F., Righetto, R. D., Lamm, L., Salinas-Giegé, T., Kelley, R., Zhang, X., Obr, M., Khavnekar, S., Kotecha, A., and Engel, B. D. (2025) _In-cell architecture of the mitochondrial respiratory chain_. Science. 387, 1296–1301, https://doi.org/10.1126/science.ads8738

