
import streamlit as st
import pandas as pd
import io
import os
import tempfile
from google.cloud import vision
import fitz  # PyMuPDF

st.set_page_config(page_title="OCR Faktur Pajak", layout="centered")

st.title("📄 OCR Faktur Pajak (PDF Scan) via Google Vision API")
st.write("Upload faktur pajak hasil scan (PDF) dan dapatkan data terstruktur dalam format Excel.")

# Upload credentials JSON
st.subheader("1. Upload Google Cloud credentials (JSON)")
cred_file = st.file_uploader("Upload service account JSON", type=["json"])

# Upload PDF faktur
st.subheader("2. Upload PDF faktur pajak (hasil scan)")
pdf_files = st.file_uploader("Upload satu atau beberapa file PDF", type=["pdf"], accept_multiple_files=True)

def parse_text(text, filename):
    import re
    rows = []
    tanggal = re.search(r'(\d{1,2} \w+ 20\d{2})', text)
    seri = re.search(r'Faktur Pajak.*?(\d{10,})', text)
    penjual = re.search(r'Nama\s*:\s*(.*?)\n.*?NPWP\s*:\s*(\d+)', text, re.DOTALL)
    pembeli = re.search(r'Pembeli.*?Nama\s*:\s*(.*?)\n.*?NPWP\s*:\s*(\d+)', text, re.DOTALL)
    dpp = re.search(r'Dasar Pengenaan Pajak\s*([\d.,]+)', text)
    ppn = re.search(r'Jumlah PPN.*?([\d.,]+)', text)
    items = re.findall(r'(\d+)\s+(.*?)\s+Rp\s*([\d.,]+)', text)

    for item in items:
        row = {
            "File": filename,
            "Tanggal Faktur": tanggal.group(1) if tanggal else '',
            "Nomor Seri": seri.group(1) if seri else '',
            "Nama Penjual": penjual.group(1).strip() if penjual else '',
            "NPWP Penjual": penjual.group(2).strip() if penjual else '',
            "Nama Pembeli": pembeli.group(1).strip() if pembeli else '',
            "NPWP Pembeli": pembeli.group(2).strip() if pembeli else '',
            "Nama Barang/Jasa": item[1].strip(),
            "Harga Jual": item[2].replace('.', '').replace(',', '.') if item[2] else '',
            "DPP": dpp.group(1).replace('.', '').replace(',', '.') if dpp else '',
            "PPN": ppn.group(1).replace('.', '').replace(',', '.') if ppn else ''
        }
        rows.append(row)
    return rows

if cred_file and pdf_files:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
        tmp.write(cred_file.read())
        cred_path = tmp.name
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_path
    vision_client = vision.ImageAnnotatorClient()

    all_data = []

    with st.spinner("🔍 Memproses dokumen..."):
        for file in pdf_files:
            pdf_bytes = file.read()
            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                for page in doc:
                    pix = page.get_pixmap(dpi=300)
                    img_bytes = pix.tobytes("png")
                    image = vision.Image(content=img_bytes)
                    response = vision_client.document_text_detection(image=image)
                    text = response.full_text_annotation.text
                    parsed = parse_text(text, file.name)
                    all_data.extend(parsed)

    if all_data:
        df = pd.DataFrame(all_data)
        st.success("✅ Faktur berhasil diproses.")
        st.dataframe(df)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Faktur Pajak")
        st.download_button("⬇ Download Excel", output.getvalue(), file_name="Hasil_OCR_Faktur.xlsx")
    else:
        st.warning("⚠️ Tidak ditemukan data dari file yang diproses.")
