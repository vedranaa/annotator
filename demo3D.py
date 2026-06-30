#!/usr/bin/env python3
"""Minimal demo for Annotator3D.
Downloads a 3D volume from the web into memory and starts annotation.
"""
#%%

import io, urllib.request, zipfile, tifffile  # for getting the volume 
import numpy as np
from annotator3D import annotate_volume

# #%% Get volume as 3D numpy array 
# # url = 'https://data.qim.dk/stdata/multicube.zip'
# url = 'https://data.qim.dk/stdata/mock.zip'
# print(f'Downloading {url} ...')
# with urllib.request.urlopen(url) as response:
#     zip_bytes = io.BytesIO(response.read())
# with zipfile.ZipFile(zip_bytes) as zf:
#     tif_names = [n for n in zf.namelist() if n.lower().endswith('.tif') or n.lower().endswith('.tiff')]
#     with zf.open(tif_names[0]) as tif_file:
#         volume = tifffile.imread(io.BytesIO(tif_file.read()))
# print(f'Loaded volume {volume.shape} dtype={volume.dtype}')

#%%

volume = tifffile.imread('data3D/bcrick.tif')
annotated_volume = annotate_volume(volume)
print(f'Annotated volume shape: {annotated_volume.shape}, dtype={annotated_volume.dtype}')

# %%
