from xml.etree import ElementTree as ET


def _text(el, tag):
    found = el.findtext(tag)
    return found.strip() if found else None


def _parse_boundary(boundary_str):
    """'lat,lng' string → (float, float) or (None, None)."""
    if not boundary_str or "," not in boundary_str:
        return None, None
    parts = boundary_str.split(",", 1)
    try:
        return float(parts[0].strip()), float(parts[1].strip())
    except ValueError:
        return None, None


def _parse_addresses(addresses_el):
    """
    Parse <addresses> block. Each <address> may have multiple <area> elements —
    collect them all into a list rather than taking only the first.
    """
    if addresses_el is None:
        return None

    result = []
    for addr_el in addresses_el.findall("address"):
        result.append({
            "type":     _text(addr_el, "address_type"),
            "line1":    _text(addr_el, "address_line"),
            "line2":    _text(addr_el, "address_line2") or None,
            "city":     _text(addr_el, "city"),
            "state":    _text(addr_el, "state"),
            "postcode": _text(addr_el, "postcode"),
            "country":  _text(addr_el, "country"),
            "areas":    [el.text.strip() for el in addr_el.findall("area") if el.text],
            "region":   _text(addr_el, "region"),
        })
    return result or None


def record_to_canonical(product_el: ET.Element) -> dict:
    """Map a <product_record> XML element to the canonical listing shape."""
    lat, lng = _parse_boundary(_text(product_el, "boundary") or "")

    return {
        "source_id":          _text(product_el, "product_id"),
        "source_number":      _text(product_el, "product_number"),
        "category":           _text(product_el, "product_category_id"),
        "status":             _text(product_el, "status"),
        "name":               _text(product_el, "product_name"),
        "description":        _text(product_el, "product_description"),
        "image_url":          _text(product_el, "product_image"),
        "latitude":           lat,
        "longitude":          lng,
        "address":            _parse_addresses(product_el.find("addresses")),
        "organisation_id":    _text(product_el, "owning_organisation_id"),
        "organisation_name":  _text(product_el, "owning_organisation_name"),
        "expires_at":         _text(product_el, "atdw_expiry_date") or None,
        "source_updated_at":  _text(product_el, "product_update_date") or None,
        "next_occurrence":    _text(product_el, "next_occurrence") or None,
    }
