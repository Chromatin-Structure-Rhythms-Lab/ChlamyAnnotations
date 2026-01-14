#!/usr/bin/env python3
import os
import argparse
import math
import numpy as np
import sys
import re
import starfile

def parse_args():
    parser = argparse.ArgumentParser(description='Generate RELION-5 tomograms.star for Chlamy dataset (EMPIAR-11830).')
    parser.add_argument('--tomos_dir', type=str, help='Directory containing tomogram folders')
    parser.add_argument('--output_dir', type=str, default='relion_star_files', help='Output directory for RELION-5 star files')
    parser.add_argument('--correspondence_star', type=str, default='tomolist_num_dir.star', help='STAR file with correspondence between tomo_num and stack_dir.',required=True)
    parser.add_argument('--ctf3d', type=str, default='ctf3d_bin4', help='Path to ctf3d tomos. It will be referenced in the output tomograms.star, but does not need to exist.')
    parser.add_argument('--cryocare', type=str, default='cryocare_bin4', help='Path to cryo-CARE denoised tomos. It will be referenced in the output tomograms.star, but does not need to exist.')
    parser.add_argument('--cosine_weight', action='store_true', default=False, help='Weight tilt images by cosine of tilt angle.')
    parser.add_argument('--include', type=str, nargs='+', default=None, 
                        help='Include only these tomogram prefixes (e.g., Position_1 Position_2)')
    parser.add_argument('--exclude', type=str, nargs='+', default=None,
                        help='Exclude these tomogram prefixes (e.g., Position_3 Position_4)')
    return parser.parse_args()

def filter_prefixes(all_prefixes, include=None, exclude=None):
    """
    Filter tomogram prefixes based on include/exclude lists.
    
    Args:
        all_prefixes: List of all detected tomogram prefixes
        include: List of prefixes to include (if None, include all)
        exclude: List of prefixes to exclude (if None, exclude none)
    
    Returns:
        Filtered list of prefixes
    """
    result = list(all_prefixes)
    
    if include is not None:
        result = [p for p in result if any(
            re.match(f"^{pattern.replace('*', '.*')}$", p) 
            for pattern in include
        )]
    
    if exclude is not None:
        result = [p for p in result if not any(
            re.match(f"^{pattern.replace('*', '.*')}$", p) 
            for pattern in exclude
        )]
        
    return result

def read_tlt_file(tomos_dir, tomo_prefix):
    """Read tilt angles from the .tlt file."""
    tlt_file = os.path.join(tomos_dir, f"{tomo_prefix}", "AreTomo", f"{tomo_prefix}_dose-filt.tlt")
    if not os.path.exists(tlt_file):
        raise FileNotFoundError(f"Tilt file not found: {tlt_file}")
    with open(tlt_file, 'r') as f:
        return [float(line.strip()) for line in f if line.strip()]

def read_xf_file(tomos_dir, tomo_prefix):
    """Read transformation matrices from the .xf file (IMOD format).

    Returns:
      A list of lists, each with 6 floats: [A11, A12, A21, A22, DX, DY].
    """
    xf_file = os.path.join(tomos_dir, f"{tomo_prefix}", "AreTomo", f"{tomo_prefix}_dose-filt.xf")
    if not os.path.exists(xf_file):
        raise FileNotFoundError(f"XF file not found: {xf_file}")
    xf_data = []
    with open(xf_file, 'r') as f:
        for line in f:
            if line.strip():
                xf_data.append([float(x) for x in line.strip().split()])
    return xf_data

def read_ctf_file(tomos_dir, tomo_prefix):
    """
    Read CTF defocus information from the _CTF.txt produced by AreTomo3 (e.g. Position_1_CTF.txt).
    Adjust parsing logic as needed if your file differs in format.
    """
    ctf_file = os.path.join(tomos_dir, f"{tomo_prefix}", "tiltctf", "ctfphaseflip_tiltctf.txt")
    if not os.path.exists(ctf_file):
        raise FileNotFoundError(f"CTF file not found: {ctf_file}")
    ctf_data = []
    with open(ctf_file, 'r') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                parts = line.strip().split()
                # Expecting something like: frame defU defV astigAngle ...
                if len(parts) == 7:
                    ctf_data.append({
                        'frame': int(parts[0]),
                        'tilt_angle': float(parts[2]),
                        'defocus_u': float(parts[4]) * 10,
                        'defocus_v': float(parts[5]) * 10,
                        'astigmatism_angle': float(parts[6])
                    })
    return ctf_data

def compute_tilt_alignment(xf_row, pixel_size):
    """
    Compute RELION tilt parameters from an IMOD .xf transformation matrix.
     Following:
     https://github.com/scipion-em/scipion-em-reliontomo/blob/8d538ca04f8d02d7a9978e594876bbf7617dcf5f/reliontomo/convert/convert50_tomo.py
     and
     https://github.com/teamtomo/yet-another-imod-wrapper/blob/main/src/yet_another_imod_wrapper/utils/xf.py#L52

    """
    A11, A12, A21, A22, DX, DY = xf_row
    # Build the full 3x3 transformation matrix
    T = np.array([[A11, A12, DX],
                  [A21, A22, DY],
                  [0.0, 0.0, 1.0]])
    # Note: np.arctan2(A12, A11) gives the proper sign.
    z_rot = np.degrees(np.arctan2(A12, A11))
    
    # Invert the full transformation matrix to get the corrected translation
    T_inv = np.linalg.inv(T)
    # The translation (shift) is given by the third column of the inverted matrix
    x_shift_angst = T_inv[0, 2] * pixel_size
    y_shift_angst = T_inv[1, 2] * pixel_size

    x_tilt = 0.0  # by default
    y_tilt = 0.0  # we populate this later
    
    return x_tilt, y_tilt, z_rot, x_shift_angst, y_shift_angst

def read_acquisition_order_dose_star(tomos_dir, tomo_prefix):
    """
    Read the tilt acquisition order from e.g. "Position_1_order_list.csv",
    which typically has 2 columns: ImageNumber, TiltAngle.
    """
    order_file = os.path.join(tomos_dir, f"{tomo_prefix}", "metadata", "tomolist", "collected_tilts.star")
    dose_file = os.path.join(tomos_dir, f"{tomo_prefix}", "metadata", "tomolist", "dose.star")
    removed_file = os.path.join(tomos_dir, f"{tomo_prefix}", "metadata", "tomolist", "removed_tilts.star")
    acquisition_order = starfile.read(order_file)
    dose = starfile.read(dose_file)
    removed = starfile.read(removed_file)
    if not os.path.exists(order_file):
        raise FileNotFoundError(f"Acquisition order STAR file not found: {order_file}")

    acquisition_data = []
    k = 1
    for i in np.arange(len(acquisition_order['collected_tilts'])):
        excluded = False
        for j in np.arange(len(removed['removed_tilts'])):
            if np.isclose(acquisition_order.loc[i,'collected_tilts'], removed.loc[j,'removed_tilts']):
                excluded = True
                break
        if not excluded:
            acquisition_data.append((k, acquisition_order.loc[i,'collected_tilts'], dose.loc[i,'dose'] ))
            k += 1

    if not acquisition_data:
        raise ValueError(f"No valid data found in acquisition order STAR file: {order_file}")
    return np.array(acquisition_data)

def create_softlinks(tomos_dir, output_dir, tomo_prefix, ctf3d_path, cryocare_path):
    """
    Create softlinks with .mrcs extension for .mrc files. This helps RELION treat them as stacks.
    """
    os.makedirs(os.path.join(output_dir, tomo_prefix) , exist_ok=True)
    abs_tomos_dir = os.path.abspath(tomos_dir)
    abs_output_dir = os.path.abspath(output_dir)

    mrc_file = os.path.join(abs_tomos_dir, tomo_prefix, f"{tomo_prefix}.st")
    evn_file = os.path.join(abs_tomos_dir, tomo_prefix, f"{tomo_prefix}_EVN.st")
    odd_file = os.path.join(abs_tomos_dir, tomo_prefix, f"{tomo_prefix}_ODD.st")
    ctf_file = os.path.join(abs_tomos_dir, tomo_prefix, "tiltctf", f"diagnostic_{tomo_prefix}_dose-filt_tiltctf_ps.mrc")
    # vol_file = os.path.join(abs_tomos_dir, tomo_prefix, f"{tomo_prefix}_Vol.mrc")

    mrc_link = os.path.join(abs_output_dir, tomo_prefix, f"{tomo_prefix}.mrcs")
    evn_link = os.path.join(abs_output_dir, tomo_prefix, f"{tomo_prefix}_EVN.mrcs")
    odd_link = os.path.join(abs_output_dir, tomo_prefix, f"{tomo_prefix}_ODD.mrcs")
    ctf_link = os.path.join(abs_output_dir, tomo_prefix, f"{tomo_prefix}_CTF.mrcs")

    links_created = []
    for src, dst in [
        (mrc_file, mrc_link),
        (evn_file, evn_link),
        (odd_file, odd_link),
        (ctf_file, ctf_link)
    ]:
        if os.path.exists(src):
            if os.path.exists(dst):
                os.remove(dst)
            print(f"Creating softlink: {dst} -> {src}")
            os.symlink(src, dst)
            links_created.append((src, dst))
            # print(f"Created softlink: {dst} -> {src}")
        else:
            print(f"Warning: Source file not found: {src}")

    return links_created

def create_dummy_edf_file(output_dir, tomo_prefix):
    """
    Create a dummy ETOMO directive (.edf) file for the tomogram.
    """
    edf_file_path = os.path.join(output_dir, f"{tomo_prefix}.edf")
    
    # Create an empty file or with minimal content
    with open(edf_file_path, 'w') as f:
        f.write("# Dummy ETOMO directive file for RELION5\n")
        f.write(f"# Generated for tomogram: {tomo_prefix}\n")
        f.write("# This is a placeholder file\n")
    
    print(f"Created dummy ETOMO directive file: {edf_file_path}")
    return edf_file_path

def collect_tomogram_data(tomos_dir, tomo_prefix, tomolist, ctf3d_path, cryocare_path,
                          nominal_tilt_axis = -85.00,
                          defHand = +1,
                          voltage = 300.0,
                          cs = 2.7,
                          amp_contrast = 0.07,
                          pixel_size = 1.96,
                          bin_factor = 4,
                          vol_size = [1024, 1024, 512],
                          dose_per_tilt = 3.5,
                          cosine_weighting = False
                          ):
    """Process a single tomogram and return its data"""
    try:
    # session_data = read_session_json(tomos_dir, tomo_prefix)
        sel = tomolist['tomoman_stack_dir'] == tomo_prefix
        tomo_num = tomolist.loc[sel, 'tomoman_tomo_num'].iloc[0]

        tilt_angles = read_tlt_file(tomos_dir, tomo_prefix)
        print(f"Found {len(tilt_angles)} tilt angles")

        xf_data = read_xf_file(tomos_dir, tomo_prefix)
        print(f"Found {len(xf_data)} transformation matrices")

        ctf_data = read_ctf_file(tomos_dir, tomo_prefix)
        print(f"Found {len(ctf_data)} CTF entries")

        vol_size_x, vol_size_y, vol_size_z = vol_size[0], vol_size[1], vol_size[2]
        
        # Assume vol file path
        vol_file = os.path.join(ctf3d_path, f"{tomo_num:d}.rec")
        denoised_vol_file = os.path.join(cryocare_path, f"{tomo_num:d}.mrc")
        
        # Handle tilt series data
        # If the CTF entries do not have tilt_angle set, match them by frame index
        if ctf_data and ctf_data[0].get('tilt_angle') is None:
            for entry in ctf_data:
                frame_idx = entry['frame'] - 1
                if 0 <= frame_idx < len(tilt_angles):
                    entry['tilt_angle'] = tilt_angles[frame_idx]

        # Attempt to read real acquisition order from STAR file
        try:
            # acquisition_order = read_acquisition_order_csv(tomos_dir, tomo_prefix)
            acquisition_order = read_acquisition_order_dose_star(tomos_dir, tomo_prefix)
            print(f"Found acquisition order data with {len(acquisition_order)} entries.")
            # exposures = calculate_cumulative_exposure(tilt_angles, acquisition_order, dose_per_tilt)
            # Sort by tilt angle to match the .tlt file:
            acquisition_order = acquisition_order[acquisition_order[:,1].argsort()]
            exposures = acquisition_order[:,2]
        except FileNotFoundError:
            print("Warning: Acquisition order CSV file not found. Using default incremental exposure.")
            # Fallback: just do an incremental from 0, 1*dose, 2*dose, ...
            exposures = [i * dose_per_tilt for i in range(len(tilt_angles))]
            
        # Create a tilt series data array
        tilt_series_data = []
        
        # Loop through the tilt angles, in sorted order (the .tlt order)
        for i, tilt_angle in enumerate(tilt_angles):
            # pre-exposure from the computed exposures array
            pre_exposure = exposures[i]

            # Attempt to match a defocus from ctf_data by tilt angle
            defocus_u = 0.0
            defocus_v = 0.0
            astigmatism_angle = 0.0
            for ctf_entry in ctf_data:
                if ctf_entry.get('tilt_angle') is not None:
                    if abs(ctf_entry['tilt_angle'] - tilt_angle) < 0.1:
                        defocus_u = ctf_entry['defocus_u']
                        defocus_v = ctf_entry['defocus_v']
                        astigmatism_angle = ctf_entry['astigmatism_angle']
                        break
                else:
                    # if no tilt_angle field, attempt frame-based
                    if ctf_entry['frame'] == (i + 1):
                        defocus_u = ctf_entry['defocus_u']
                        defocus_v = ctf_entry['defocus_v']
                        astigmatism_angle = ctf_entry['astigmatism_angle']
                        break

            astigmatism = abs(defocus_u - defocus_v)
            defocus_angle = astigmatism_angle

            x_tilt, _, z_rot, x_shift_angst, y_shift_angst = compute_tilt_alignment(xf_data[i], pixel_size)
            y_tilt = tilt_angle

            # For typical single-tilt geometry, you might scale some factors with cos(tilt)
            if cosine_weighting:
                ctf_scalefactor = math.cos(math.radians(tilt_angle))
            else:
                ctf_scalefactor = 1.0
            
            tilt_series_data.append({
                'index': i,
                'tilt_angle': tilt_angle,
                'pre_exposure': pre_exposure,
                'defocus_u': defocus_u,
                'defocus_v': defocus_v,
                'astigmatism': astigmatism,
                'defocus_angle': defocus_angle,
                'x_tilt': x_tilt,
                'y_tilt': y_tilt,
                'z_rot': z_rot,
                'x_shift_angst': x_shift_angst,
                'y_shift_angst': y_shift_angst,
                'ctf_scalefactor': ctf_scalefactor
            })
        
        return {
            'prefix': tomo_prefix,
            'voltage': voltage,
            'cs': cs,
            'amp_contrast': amp_contrast,
            'pixel_size': pixel_size,
            'hand': defHand,
            'bin_factor': bin_factor,
            'vol_size_x': vol_size_x,
            'vol_size_y': vol_size_y,
            'vol_size_z': vol_size_z,
            'tilt_axis': nominal_tilt_axis,
            'vol_file': vol_file,
            'denoised_vol_file': denoised_vol_file,
            'tilt_series_data': tilt_series_data,
            'tomo_num': tomo_num
        }
    
    except Exception as e:
        print(f"Error processing tomogram {tomo_prefix}: {str(e)}")
        return None

def create_combined_tomogram_star(tomogram_data_list, output_dir):
    """
    Create a combined tomograms.star file for all tomograms.
    """
    tomogram_star_path = os.path.join(output_dir, 'tomograms.star')
    
    with open(tomogram_star_path, 'w') as f:
        f.write("# version 50001\n\n")
        f.write("data_global\n\n")
        f.write("loop_\n")
        f.write("_rlnTomoName #1\n")
        f.write("_rlnVoltage #2\n")
        f.write("_rlnSphericalAberration #3\n")
        f.write("_rlnAmplitudeContrast #4\n")
        f.write("_rlnMicrographOriginalPixelSize #5\n")
        f.write("_rlnTomoHand #6\n")
        f.write("_rlnOpticsGroupName #7\n")
        f.write("_rlnTomoTiltSeriesPixelSize #8\n")
        f.write("_rlnTomoTiltSeriesStarFile #9\n")
        f.write("_rlnEtomoDirectiveFile #10\n")
        f.write("_rlnTomoTomogramBinning #11\n")
        f.write("_rlnTomoSizeX #12\n")
        f.write("_rlnTomoSizeY #13\n")
        f.write("_rlnTomoSizeZ #14\n")
        f.write("_rlnTomoReconstructedTomogram #15\n")
        f.write("_rlnTomoDenoisedTomogram #16\n")
        f.write("_tomoman_tomo_num #17\n")

        for data in tomogram_data_list:
            if data is None:
                continue
                
            tomo_prefix = data['prefix']
            optics_group = "optics1"  # Default optics group
            
            # Relative paths for star and etomo directive files
            tilt_series_star_rel = f"{tomo_prefix}.star"
            etomo_directive_rel = f"{tomo_prefix}.edf"

            f.write(
                f"{tomo_prefix}   {data['voltage']:.6f}   {data['cs']:.6f}   {data['amp_contrast']:.6f}   "
                f"{data['pixel_size']:.6f}   {data['hand']:.6f}   {optics_group}   {data['pixel_size']:.6f}   "
                f"{tilt_series_star_rel}   {etomo_directive_rel}   {data['bin_factor']:.6f}   "
                f"{data['vol_size_x']}   {data['vol_size_y']}   {data['vol_size_z']}   {data['vol_file']} {data['denoised_vol_file']} {data['tomo_num']}\n"
            )
            
    print(f"Created combined tomogram star file: {tomogram_star_path}")
    return tomogram_star_path

def create_individual_tilt_series_star(tomogram_data, output_dir):
    """
    Create an individual tilt-series star file for a single tomogram.
    """
    tomo_prefix = tomogram_data['prefix']
    pixel_size = tomogram_data['pixel_size']
    tilt_axis = tomogram_data['tilt_axis']
    
    abs_output_dir = os.path.abspath(os.path.join(output_dir, tomo_prefix))
    even_mrcs_file = os.path.join(abs_output_dir, f"{tomo_prefix}_EVN.mrcs")
    odd_mrcs_file = os.path.join(abs_output_dir, f"{tomo_prefix}_ODD.mrcs")
    aligned_mrcs_file = os.path.join(abs_output_dir, f"{tomo_prefix}.mrcs")
    ctf_mrcs_file = os.path.join(abs_output_dir, f"{tomo_prefix}_CTF.mrcs")
    
    tilt_series_star_path = os.path.join(output_dir, f"{tomo_prefix}.star")
    
    with open(tilt_series_star_path, 'w') as f:
        f.write("# Exporting Chlamy dataset to RELION-5\n")
        f.write("# Relion star file version 50001\n\n")
        f.write(f"data_{tomo_prefix}\n\n")

        # Define the columns in the standard RELION tilt-series star format
        f.write("loop_\n")
        f.write("_rlnMicrographMovieName\n")
        f.write("_rlnTomoTiltMovieFrameCount\n")
        f.write("_rlnTomoNominalStageTiltAngle\n")
        f.write("_rlnTomoNominalTiltAxisAngle\n")
        f.write("_rlnMicrographPreExposure\n")
        f.write("_rlnTomoNominalDefocus\n")
        f.write("_rlnCtfPowerSpectrum\n")
        f.write("_rlnMicrographNameEven\n")
        f.write("_rlnMicrographNameOdd\n")
        f.write("_rlnMicrographName\n")
        f.write("_rlnMicrographMetadata\n")
        f.write("_rlnAccumMotionTotal\n")
        f.write("_rlnAccumMotionEarly\n")
        f.write("_rlnAccumMotionLate\n")
        f.write("_rlnCtfImage\n")
        f.write("_rlnDefocusU\n")
        f.write("_rlnDefocusV\n")
        f.write("_rlnCtfAstigmatism\n")
        f.write("_rlnDefocusAngle\n")
        f.write("_rlnCtfFigureOfMerit\n")
        f.write("_rlnCtfMaxResolution\n")
        f.write("_rlnCtfIceRingDensity\n")
        f.write("_rlnTomoXTilt\n")
        f.write("_rlnTomoYTilt\n")
        f.write("_rlnTomoZRot\n")
        f.write("_rlnTomoXShiftAngst\n")
        f.write("_rlnTomoYShiftAngst\n")
        f.write("_rlnCtfScalefactor\n\n")
        
        # For each tilt image in this tomogram:
        for entry in tomogram_data['tilt_series_data']:
            # Extract parameters from the tilt series data structure
            i = entry['index']
            tilt_angle = entry['tilt_angle']
            pre_exposure = entry['pre_exposure']
            defocus_u = entry['defocus_u']
            defocus_v = entry['defocus_v']
            astigmatism = entry['astigmatism']
            defocus_angle = entry['defocus_angle']
            x_tilt = entry['x_tilt']
            y_tilt = entry['y_tilt']
            z_rot = entry['z_rot']
            x_shift_angst = entry['x_shift_angst']
            y_shift_angst = entry['y_shift_angst']
            ctf_scalefactor = entry['ctf_scalefactor']
            
            even_entry = f"{(i+1):06d}@{even_mrcs_file}"
            odd_entry = f"{(i+1):06d}@{odd_mrcs_file}"
            aligned_entry = f"{i+1}@{aligned_mrcs_file}"
            ctf_entry_str = f"{i+1}@{ctf_mrcs_file}"
            
            # Write the row
            f.write(
                f"FileNotFound 1 {tilt_angle:.6f} {tilt_axis:.6f} {pre_exposure:.6f} 0.000000 FileNotFound "
                f"{even_entry} {odd_entry} {aligned_entry} FileNotFound 0 0 0 {ctf_entry_str} "
                f"{defocus_u:.6f} {defocus_v:.6f} {astigmatism:.6f} {defocus_angle:.6f} 0 "
                f"10.000000 0.010000 {x_tilt:.6f} {y_tilt:.6f} {z_rot:.6f} {x_shift_angst:.6f} {y_shift_angst:.6f} {ctf_scalefactor:.6f}\n"
            )
    
    print(f"Created individual tilt series star file: {tilt_series_star_path}")
    return tilt_series_star_path

def main():
    args = parse_args()
    
    if not os.path.exists(args.tomos_dir):
        print(f"Error: AreTomo3 directory not found: {args.tomos_dir}", file=sys.stderr)
        sys.exit(1)
    
    os.makedirs(args.output_dir, exist_ok=True)

    tomolist = starfile.read(args.correspondence_star)
    
    # Find and filter tomogram prefixes
    # all_prefixes = find_all_tomo_prefixes(args.tomos_dir)
    all_prefixes = os.listdir(args.tomos_dir)
    tomo_prefixes = filter_prefixes(all_prefixes, args.include, args.exclude)
    
    if not tomo_prefixes:
        print("No tomogram prefixes found matching the criteria.", file=sys.stderr)
        sys.exit(1)
    
    print("Processing tomograms:")
    for prefix in tomo_prefixes:
        print(f"  {prefix}")
    
    # Process each tomogram folder and collect data into a list
    tomogram_data_list = []
    for prefix in tomo_prefixes:
        # Create softlinks for the current tomogram
        try:
            create_softlinks(args.tomos_dir, args.output_dir, prefix, args.ctf3d, args.cryocare)
        except Exception as e:
            print(f"Warning: Could not create softlinks for {prefix}: {e}")
            continue
        data = collect_tomogram_data(args.tomos_dir, prefix, tomolist, args.ctf3d, args.cryocare, cosine_weighting=args.cosine_weight)
        if data is None:
            print(f"Skipping tomogram {prefix} due to errors.")
            continue
        tomogram_data_list.append(data)
        
        # Create an individual tilt-series star file for this tomogram
        create_individual_tilt_series_star(data, args.output_dir)

        create_dummy_edf_file(args.output_dir, prefix)
    
    # Create a combined tomogram.star file (including all tomograms)
    if tomogram_data_list:
        create_combined_tomogram_star(tomogram_data_list, args.output_dir)
    else:
        print("No valid tomogram data was collected.", file=sys.stderr)
    
    print("Processing completed.")

if __name__ == "__main__":
    main()
