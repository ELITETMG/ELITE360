import io
import json
import csv
import zipfile
import tempfile
import os
from typing import List, Dict, Tuple, Optional
from lxml import etree

KML_NS = {'kml': 'http://www.opengis.net/kml/2.2'}


def _kml_color_to_rgb(kml_color: str) -> Tuple[Optional[str], Optional[float]]:
    """Convert KML AABBGGRR hex color to (#RRGGBB, opacity 0-1)."""
    kml_color = kml_color.strip().lstrip('#')
    if len(kml_color) != 8:
        return None, None
    try:
        aa = kml_color[0:2]
        bb = kml_color[2:4]
        gg = kml_color[4:6]
        rr = kml_color[6:8]
        rgb = f"#{rr}{gg}{bb}"
        opacity = round(int(aa, 16) / 255.0, 2)
        return rgb, opacity
    except (ValueError, IndexError):
        return None, None


def _parse_kml_styles(root) -> Dict[str, Dict]:
    """Parse Style and StyleMap elements from KML root, return dict keyed by style id."""
    ns = '{http://www.opengis.net/kml/2.2}'
    styles = {}

    for style_el in root.iter(f'{ns}Style'):
        style_id = style_el.get('id')
        if not style_id:
            continue
        styles[style_id] = _extract_style_props(style_el, ns)

    style_maps = {}
    for sm in root.iter(f'{ns}StyleMap'):
        sm_id = sm.get('id')
        if not sm_id:
            continue
        for pair in sm.findall(f'{ns}Pair'):
            key_el = pair.find(f'{ns}key')
            if key_el is not None and key_el.text and key_el.text.strip() == 'normal':
                url_el = pair.find(f'{ns}styleUrl')
                if url_el is not None and url_el.text:
                    ref = url_el.text.strip().lstrip('#')
                    if ref in styles:
                        style_maps[sm_id] = styles[ref]
                style_inline = pair.find(f'{ns}Style')
                if style_inline is not None and sm_id not in style_maps:
                    style_maps[sm_id] = _extract_style_props(style_inline, ns)
                break

    styles.update(style_maps)
    return styles


def _extract_style_props(style_el, ns: str) -> Dict:
    """Extract color, width, opacity, icon from a Style element."""
    props = {}
    line_style = style_el.find(f'{ns}LineStyle')
    if line_style is not None:
        color_el = line_style.find(f'{ns}color')
        if color_el is not None and color_el.text:
            rgb, opacity = _kml_color_to_rgb(color_el.text)
            if rgb:
                props['style_color'] = rgb
            if opacity is not None:
                props['style_opacity'] = opacity
        width_el = line_style.find(f'{ns}width')
        if width_el is not None and width_el.text:
            try:
                props['style_width'] = float(width_el.text.strip())
            except ValueError:
                pass

    poly_style = style_el.find(f'{ns}PolyStyle')
    if poly_style is not None and 'style_color' not in props:
        color_el = poly_style.find(f'{ns}color')
        if color_el is not None and color_el.text:
            rgb, opacity = _kml_color_to_rgb(color_el.text)
            if rgb:
                props['style_color'] = rgb
            if opacity is not None and 'style_opacity' not in props:
                props['style_opacity'] = opacity

    icon_style = style_el.find(f'{ns}IconStyle')
    if icon_style is not None:
        icon_el = icon_style.find(f'{ns}Icon')
        if icon_el is not None:
            href_el = icon_el.find(f'{ns}href')
            if href_el is not None and href_el.text:
                props['style_icon'] = href_el.text.strip()[:50]

    return props


def parse_kml_content(content: bytes) -> List[Dict]:
    """Parse KML XML content into feature dicts."""
    features = []
    try:
        parser = etree.XMLParser(resolve_entities=False, no_network=True)
        root = etree.fromstring(content, parser=parser)
    except etree.XMLSyntaxError as e:
        raise ValueError(f"Invalid KML: {str(e)}")
    
    doc_styles = _parse_kml_styles(root)
    
    for placemark in root.iter('{http://www.opengis.net/kml/2.2}Placemark'):
        feature = {}
        name_el = placemark.find('kml:name', KML_NS)
        desc_el = placemark.find('kml:description', KML_NS)
        feature['name'] = name_el.text if name_el is not None and name_el.text else 'Unnamed'
        feature['description'] = desc_el.text if desc_el is not None and desc_el.text else None
        
        props = {}
        for data in placemark.iter('{http://www.opengis.net/kml/2.2}Data'):
            key = data.get('name', '')
            val_el = data.find('kml:value', KML_NS)
            if key and val_el is not None and val_el.text:
                props[key] = val_el.text
        for sdata in placemark.iter('{http://www.opengis.net/kml/2.2}SimpleData'):
            key = sdata.get('name', '')
            if key and sdata.text:
                props[key] = sdata.text
        feature['properties'] = props
        
        geom = None
        point = placemark.find('.//kml:Point/kml:coordinates', KML_NS)
        if point is not None and point.text:
            coords = point.text.strip().split(',')
            geom = {"type": "Point", "coordinates": [float(coords[0]), float(coords[1])]}
        
        linestring = placemark.find('.//kml:LineString/kml:coordinates', KML_NS)
        if linestring is not None and linestring.text:
            coord_pairs = linestring.text.strip().split()
            coords = []
            for pair in coord_pairs:
                parts = pair.split(',')
                coords.append([float(parts[0]), float(parts[1])])
            geom = {"type": "LineString", "coordinates": coords}
        
        polygon = placemark.find('.//kml:Polygon//kml:coordinates', KML_NS)
        if polygon is not None and polygon.text:
            coord_pairs = polygon.text.strip().split()
            coords = []
            for pair in coord_pairs:
                parts = pair.split(',')
                coords.append([float(parts[0]), float(parts[1])])
            geom = {"type": "Polygon", "coordinates": [coords]}
        
        multigeom = placemark.find('.//kml:MultiGeometry', KML_NS)
        if multigeom is not None and geom is None:
            mp = multigeom.find('.//kml:Point/kml:coordinates', KML_NS)
            if mp is not None and mp.text:
                coords = mp.text.strip().split(',')
                geom = {"type": "Point", "coordinates": [float(coords[0]), float(coords[1])]}
            ml = multigeom.find('.//kml:LineString/kml:coordinates', KML_NS)
            if ml is not None and ml.text:
                coord_pairs = ml.text.strip().split()
                coords = [[float(p.split(',')[0]), float(p.split(',')[1])] for p in coord_pairs]
                geom = {"type": "LineString", "coordinates": coords}
        
        feature['geometry'] = geom
        
        style_props = {}
        style_url_el = placemark.find('kml:styleUrl', KML_NS)
        if style_url_el is not None and style_url_el.text:
            ref = style_url_el.text.strip().lstrip('#')
            if ref in doc_styles:
                style_props = dict(doc_styles[ref])
        inline_style = placemark.find('kml:Style', KML_NS)
        if inline_style is not None:
            inline_props = _extract_style_props(inline_style, '{http://www.opengis.net/kml/2.2}')
            style_props.update(inline_props)
        for sk in ('style_color', 'style_width', 'style_opacity', 'style_icon'):
            if sk in style_props:
                feature[sk] = style_props[sk]
        
        features.append(feature)
    
    return features


def parse_kmz(content: bytes) -> List[Dict]:
    """Extract KML from KMZ (ZIP) and parse."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            kml_files = [f for f in zf.namelist() if f.lower().endswith('.kml')]
            if not kml_files:
                raise ValueError("No KML file found in KMZ archive")
            kml_content = zf.read(kml_files[0])
            return parse_kml_content(kml_content)
    except zipfile.BadZipFile:
        raise ValueError("Invalid KMZ file (not a valid ZIP archive)")


def parse_shapefile_zip(content: bytes) -> List[Dict]:
    """Parse a ZIP containing .shp/.dbf/.shx files using Fiona."""
    import fiona
    features = []
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "upload.zip")
            with open(zip_path, 'wb') as f:
                f.write(content)
            
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(tmpdir)
            
            shp_files = []
            for root_dir, dirs, files in os.walk(tmpdir):
                for f in files:
                    if f.lower().endswith('.shp'):
                        shp_files.append(os.path.join(root_dir, f))
            
            if not shp_files:
                raise ValueError("No .shp file found in ZIP archive")
            
            with fiona.open(shp_files[0]) as src:
                for feat in src:
                    geom = dict(feat.get('geometry', {})) if feat.get('geometry') else None
                    props = dict(feat.get('properties', {}))
                    name = props.get('name') or props.get('NAME') or props.get('Name') or props.get('id') or props.get('ID') or 'Unnamed'
                    desc = props.get('description') or props.get('DESCRIPTION') or props.get('desc') or None
                    features.append({
                        'name': str(name),
                        'description': str(desc) if desc else None,
                        'geometry': geom,
                        'properties': {k: str(v) if v is not None else None for k, v in props.items()}
                    })
    except Exception as e:
        if "No .shp file" in str(e) or "Invalid" in str(e):
            raise
        raise ValueError(f"Error reading Shapefile: {str(e)}")
    
    return features


def parse_dxf(content: bytes) -> List[Dict]:
    """Parse DXF CAD file using ezdxf."""
    import ezdxf
    features = []
    try:
        doc = ezdxf.read(io.BytesIO(content))
        msp = doc.modelspace()
        
        for entity in msp:
            geom = None
            name = entity.dxf.get('layer', 'Unnamed')
            props = {'layer': name, 'dxf_type': entity.dxftype()}
            
            if entity.dxftype() == 'POINT':
                pt = entity.dxf.insert if hasattr(entity.dxf, 'insert') else entity.dxf.location
                geom = {"type": "Point", "coordinates": [pt.x, pt.y]}
            elif entity.dxftype() == 'LINE':
                start = entity.dxf.start
                end = entity.dxf.end
                geom = {"type": "LineString", "coordinates": [[start.x, start.y], [end.x, end.y]]}
            elif entity.dxftype() == 'LWPOLYLINE':
                coords = [[p[0], p[1]] for p in entity.get_points(format='xy')]
                if len(coords) >= 2:
                    if entity.closed:
                        coords.append(coords[0])
                        geom = {"type": "Polygon", "coordinates": [coords]}
                    else:
                        geom = {"type": "LineString", "coordinates": coords}
            elif entity.dxftype() == 'POLYLINE':
                coords = [[v.dxf.location.x, v.dxf.location.y] for v in entity.vertices]
                if len(coords) >= 2:
                    if entity.is_closed:
                        coords.append(coords[0])
                        geom = {"type": "Polygon", "coordinates": [coords]}
                    else:
                        geom = {"type": "LineString", "coordinates": coords}
            elif entity.dxftype() == 'CIRCLE':
                center = entity.dxf.center
                geom = {"type": "Point", "coordinates": [center.x, center.y]}
                props['radius'] = entity.dxf.radius
            elif entity.dxftype() == 'SPLINE':
                try:
                    coords = [[p.x, p.y] for p in entity.control_points]
                    if len(coords) >= 2:
                        geom = {"type": "LineString", "coordinates": coords}
                except:
                    pass
            
            if geom:
                features.append({
                    'name': name,
                    'description': None,
                    'geometry': geom,
                    'properties': props
                })
    except Exception as e:
        raise ValueError(f"Error reading DXF file: {str(e)}")
    
    return features


def detect_format(filename: str) -> str:
    """Detect file format from extension."""
    ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
    format_map = {
        'csv': 'csv',
        'geojson': 'geojson',
        'json': 'geojson',
        'kml': 'kml',
        'kmz': 'kmz',
        'zip': 'shapefile',
        'dxf': 'dxf',
    }
    return format_map.get(ext, 'unknown')


def parse_file(content: bytes, file_format: str) -> Tuple[List[Dict], str]:
    """
    Unified parser - returns (features, format_name).
    Each feature dict has: name, description, geometry (GeoJSON dict), properties (dict)
    """
    if file_format == 'kml':
        return parse_kml_content(content), 'kml'
    elif file_format == 'kmz':
        return parse_kmz(content), 'kmz'
    elif file_format == 'shapefile':
        return parse_shapefile_zip(content), 'shapefile'
    elif file_format == 'dxf':
        return parse_dxf(content), 'dxf'
    elif file_format == 'geojson':
        try:
            data = json.loads(content.decode('utf-8'))
            features = []
            raw_features = data.get('features', []) if data.get('type') == 'FeatureCollection' else [data] if data.get('type') == 'Feature' else []
            for f in raw_features:
                props = f.get('properties', {}) or {}
                features.append({
                    'name': props.get('name') or props.get('Name') or props.get('NAME') or props.get('id') or 'Unnamed',
                    'description': props.get('description') or props.get('desc') or None,
                    'geometry': f.get('geometry'),
                    'properties': props
                })
            return features, 'geojson'
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ValueError(f"Invalid GeoJSON: {str(e)}")
    elif file_format == 'csv':
        try:
            text = content.decode('utf-8')
            reader = csv.DictReader(io.StringIO(text))
            features = []
            for row in reader:
                geom = None
                if row.get('geometry'):
                    try:
                        geom = json.loads(row['geometry'])
                    except json.JSONDecodeError:
                        pass
                elif row.get('longitude') and row.get('latitude'):
                    try:
                        geom = {"type": "Point", "coordinates": [float(row['longitude']), float(row['latitude'])]}
                    except ValueError:
                        pass
                
                features.append({
                    'name': row.get('name', 'Unnamed'),
                    'description': row.get('description'),
                    'geometry': geom,
                    'properties': dict(row)
                })
            return features, 'csv'
        except (UnicodeDecodeError, csv.Error) as e:
            raise ValueError(f"Invalid CSV: {str(e)}")
    else:
        raise ValueError(f"Unsupported file format: {file_format}")
