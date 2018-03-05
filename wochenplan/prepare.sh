filename=wochenplan.doc

libreoffice --headless --convert-to html:HTML "${filename}"

filename="${filename%.*}.html"

sed -i -E '1d;/<col.*>/d;s|style=[^>]+style=[^>]+||g' "${filename}"
