# FORCAR LIMPEZA DE CACHE - TENTATIVA FINAL
import streamlit as st
from PIL import Image, ImageOps, ImageEnhance
import easyocr
import numpy as np
import pandas as pd
import re
import os
from difflib import get_close_matches
from datetime import datetime

# 1. Configuração
st.set_page_config(page_title="Pag Certo v5.0 (Dossiê)", page_icon="🛡️", layout="wide")
ARQUIVO_HISTORICO = 'historico_compras.csv'
ARQUIVO_ERROS = 'dossie_erros.csv'

# 2. Cérebro
@st.cache_resource
def load_reader():
    # Carrega o leitor de OCR
    return easyocr.Reader(['pt'], gpu=False)

def processar_imagem(img):
    # 1. CORREÇÃO DE ROTAÇÃO (RESOLVE O PROBLEMA DA FOTO DEITADA)
    img = ImageOps.exif_transpose(img) 
    
    # 2. FORÇA MÁXIMA NA NITIDEZ (RESOLVE O PROBLEMA DO DESFOQUE/BORRÃO)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    
    # 3. ESCALA DE CINZA
    img = ImageOps.grayscale(img)
    
    # 4. CONTRASTE AGRESSIVO
    img = ImageEnhance.Contrast(img).enhance(2.5) 
    
    return img

def ler_texto_completo(img):
    reader = load_reader()
    return reader.readtext(np.array(img), detail=0, paragraph=False)

def extrair_produtos(lista_texto):
    produtos = []
    # Blacklist expandida para ignorar linhas de rodapé
    blacklist = ["TOTAL", "SUBTOTAL", "TROCO", "DINHEIRO", "EMISSAO", "CNPJ", "PAGUE", "MENOS", "VALOR", "ITEM", "CREDITO", "DEBITO", "IMPOSTO", "TRIBUTO"]
    
    for i, linha in enumerate(lista_texto):
        t = str(linha).strip().upper()
        # Busca por padrões de preço (XX.XX ou XX,XX)
        match = re.search(r'(\d+)\s*[,.]\s*(\d{2})\b', t)
        if match:
            try:
                val = float(f"{match.group(1)}.{match.group(2)}")
                # Pega a linha anterior como nome do produto
                nom = str(lista_texto[i-1]).strip().upper() if i > 0 else "ITEM"
                nom = re.sub(r'^[^A-Z0-9]+', '', nom)
                
                if not any(b in nom for b in blacklist) and val > 0 and len(nom) > 2:
                    produtos.append({"Produto": nom, "Valor": val})
            except: pass
    return produtos

# 3. Estado (Memória)
if 'cesta' not in st.session_state:
    st.session_state.cesta = []
if 'resultado_auditoria' not in st.session_state:
    st.session_state.resultado_auditoria = None
if 'erros_para_salvar' not in st.session_state:
    st.session_state.erros_para_salvar = None

# 4. Interface
st.title("🛡️ Pag Certo - Sistema de Defesa do Consumidor")

# BARRA LATERAL
with st.sidebar:
    st.header("🛒 Cesta de Gôndola")
    if st.button("🗑️ LIMPAR CESTA ATUAL", type="primary"):
        st.session_state.cesta = []
        st.session_state.resultado_auditoria = None
        st.session_state.erros_para_salvar = None
        st.rerun()
    
    if st.session_state.cesta:
        df = pd.DataFrame(st.session_state.cesta)
        st.metric("Total Gôndola", f"R$ {df['Valor'].sum():.2f}")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Cesta vazia.")

    st.divider()
    st.header("📂 Dados Salvos")
    if os.path.exists(ARQUIVO_ERROS):
        df_erros = pd.read_csv(ARQUIVO_ERROS)
        st.error(f"🚨 {len(df_erros)} Erros Registrados!")

# ABAS
aba1, aba2, aba3 = st.tabs(["1️⃣ GÔNDOLA (Captura)", "2️⃣ CAIXA (Auditoria)", "3️⃣ DOSSIÊ (Histórico)"])

# --- ABA 1: GÔNDOLA ---
with aba1:
    st.write("### O que você viu na prateleira?")
    col_cam, col_up = st.columns(2)
    img_gondola = None
    
    # Opção Câmera
    with col_cam:
        c = st.camera_input("📸 Câmera")
        if c: 
            img_aberta = Image.open(c)
            img_gondola = processar_imagem(img_aberta)
            
    # Opção Upload
    with col_up:
        u = st.file_uploader("📂 Arquivo", type=["jpg","png"], key="up1")
        if u: 
            img_aberta = Image.open(u)
            img_gondola = processar_imagem(img_aberta)

    if img_gondola:
        # Mostra a imagem processada (em pé e nítida)
        st.image(img_gondola, width=200, caption="Imagem Processada para Leitura")
        if st.button("➕ LER E MEMORIZAR", type="primary"):
            with st.spinner("Lendo..."):
                txt = ler_texto_completo(img_gondola)
                itens = extrair_produtos(txt)
                if itens:
                    for item in itens: st.session_state.cesta.append(item)
                    st.success(f"✅ Memorizei {len(itens)} itens!")
                    st.rerun()
                else: st.warning("Não consegui ler nada. Tente melhorar o foco/iluminação.")

# --- ABA 2: CAIXA ---
with aba2:
    st.write("### O que o mercado cobrou?")
    u_nota = st.file_uploader("📂 Foto da Nota Fiscal", type=["jpg","png"], key="up2")
    
    if u_nota:
        # Processa a imagem da nota (rotação e nitidez) para exibição e leitura
        img_nota_raw = Image.open(u_nota)
        img_nota = processar_imagem(img_nota_raw)
        st.image(img_nota, caption="Nota Fiscal Processada", width=300)
        
        if st.button("🚀 AUDITAR AGORA", type="primary"):
            if not st.session_state.cesta:
                st.error("Cesta vazia! Vá na aba 1 e capture os preços da gôndola.")
            else:
                with st.spinner("O Juiz está analisando..."):
                    txt = ler_texto_completo(img_nota)
                    itens_nota = extrair_produtos(txt)
                    
                    relatorio = []
                    erros_encontrados = []
                    
                    for item_cesta in st.session_state.cesta:
                        nome = item_cesta['Produto']
                        esperado = item_cesta['Valor']
                        # Mantendo cutoff em 0.5, mas ideal é 0.7 para maior segurança
                        matches = get_close_matches(nome, [i['Produto'] for i in itens_nota], n=1, cutoff=0.5) 
                        
                        status = "⚪ Não achado"
                        cobrado = 0.0
                        diff = 0.0
                        
                        if matches:
                            match = next(i for i in itens_nota if i['Produto'] == matches[0])
                            cobrado = match['Valor']
                            diff = cobrado - esperado
                            
                            if diff > 0.05:
                                status = f"🔴 ROUBO (+{diff:.2f})"
                                erros_encontrados.append({
                                    "Data": datetime.now().strftime("%d/%m/%Y"),
                                    "Produto": nome,
                                    "Esperado": esperado,
                                    "Cobrado": cobrado,
                                    "Prejuízo": diff
                                })
                            elif diff < -0.05: status = "🟢 Desconto"
                            else: status = "✅ OK"
                        
                        relatorio.append({"Produto": nome, "Esperado": esperado, "Cobrado": cobrado, "Status": status})
                    
                    st.session_state.resultado_auditoria = pd.DataFrame(relatorio)
                    st.session_state.erros_para_salvar = erros_encontrados
                    st.rerun() # Força a atualização da interface após a auditoria

    # MOSTRAR RESULTADO E SALVAR
    if st.session_state.resultado_auditoria is not None:
        st.write("### Veredito:")
        
        def pintar(val):
            if 'ROUBO' in str(val): return 'background-color: #ffcccc; color: red; font-weight: bold'
            if 'OK' in str(val): return 'background-color: #ccffcc'
            return ''
        
        st.dataframe(st.session_state.resultado_auditoria.style.applymap(pintar, subset=['Status']), use_container_width=True)
        
        erros = st.session_state.erros_para_salvar
        if erros:
            st.error(f"🚨 Detectamos {len(erros)} cobranças indevidas!")
            if st.button("💾 SALVAR NO DOSSIÊ DE ERROS"):
                df_erros = pd.DataFrame(erros)
                header = not os.path.exists(ARQUIVO_ERROS)
                df_erros.to_csv(ARQUIVO_ERROS, mode='a', header=header, index=False)
                st.balloons()
                st.success("✅ Prova salva no Dossiê! (Veja na Aba 3)")
                st.session_state.erros_para_salvar = [] # Limpa a memória para evitar salvar duas vezes
        else:
            st.success("Nenhum roubo detectado nesta compra.")

# --- ABA 3: DOSSIÊ (HISTÓRICO) ---
with aba3:
    st.header("📂 Dossiê de Infrações")
    st.caption("Aqui fica o histórico de todas as vezes que tentaram te cobrar a mais.")
    
    if os.path.exists(ARQUIVO_ERROS):
        df_dossie = pd.read_csv(ARQUIVO_ERROS)
        st.dataframe(df_dossie, use_container_width=True)
        
        total_roubado = df_dossie["Prejuízo"].sum()
        st.metric("Total de Prejuízo Evitado", f"R$ {total_roubado:.2f}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.download_button("📥 Baixar Relatório (CSV)", df_dossie.to_csv(index=False), "dossie.csv")
        with col2:
            if st.button("🗑️ Limpar Dossiê"):
                os.remove(ARQUIVO_ERROS)
                st.rerun()
    else:
        st.info("Seu dossiê está limpo (Nenhum erro salvo ainda).")

