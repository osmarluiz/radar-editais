"""Envia por e-mail (Gmail) os editais novos gravados pelo radar.py.

Uso: python scripts/enviar_email.py caminho/novos.json
Variáveis: GMAIL_USER (remetente e destinatário), GMAIL_APP_PASSWORD (senha de app do Google),
EMAIL_DESTINO (opcional, outros destinatários separados por vírgula), PAINEL_URL (opcional).
Sai com código 2 se o e-mail não estiver configurado, para o workflow cair no aviso por issue.
"""

import json
import os
import smtplib
import sys
from datetime import datetime
from email.message import EmailMessage
from html import escape

usuario = os.environ.get("GMAIL_USER", "").strip()
senha = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")
if not usuario or not senha:
    print("E-mail não configurado (GMAIL_USER / GMAIL_APP_PASSWORD).")
    sys.exit(2)

novos = json.loads(open(sys.argv[1], encoding="utf-8").read())
painel = os.environ.get("PAINEL_URL", "")
destino = os.environ.get("EMAIL_DESTINO", "").strip() or usuario


def data_br(iso):
    return "/".join(reversed(iso.split("-"))) if iso else "sem prazo informado"


itens_html, itens_txt = [], []
for e in novos:
    cor = "#15803d" if e["relevancia"] == "alta" else "#a16207"
    rel = "alta" if e["relevancia"] == "alta" else "média"
    titulo = escape(e["titulo"])
    if e.get("link"):
        titulo = f'<a href="{escape(e["link"])}" style="color:#1d4ed8;text-decoration:none">{titulo}</a>'
    extras = f' · {escape(e["valor"])}' if e.get("valor") else ""
    if e.get("perfis_nomes"):
        extras += f' · para <b>{escape(", ".join(e["perfis_nomes"]))}</b>'
    itens_html.append(f"""
      <div style="border-left:4px solid {cor};padding:8px 12px;margin:0 0 14px;background:#f8fafc">
        <div style="font-size:16px;font-weight:600">{titulo}</div>
        <div style="font-size:13px;color:#475569;margin:3px 0">
          {escape(e["fonte_nome"])} · prazo <b>{data_br(e.get("prazo"))}</b> ·
          <span style="color:{cor};font-weight:600">relevância {rel}</span>{extras}
        </div>
        <div style="font-size:14px">{escape(e["resumo"])}</div>
      </div>""")
    para = f", para {', '.join(e['perfis_nomes'])}" if e.get("perfis_nomes") else ""
    itens_txt.append(f"- {e['titulo']} ({e['fonte_nome']}, prazo {data_br(e.get('prazo'))}, "
                     f"relevância {rel}{para})\n  {e['resumo']}\n  {e.get('link') or ''}")

n = len(novos)
assunto = f"Radar de editais: {n} {'edital novo' if n == 1 else 'editais novos'} em {datetime.now():%d/%m/%Y}"
rodape_html = f'<p style="font-size:13px"><a href="{escape(painel)}">Abrir o painel completo</a></p>' if painel else ""

msg = EmailMessage()
msg["Subject"] = assunto
msg["From"] = f"Radar de editais <{usuario}>"
msg["To"] = destino
msg.set_content("\n\n".join(itens_txt) + (f"\n\nPainel: {painel}" if painel else ""))
msg.add_alternative(f"""<html><body style="font-family:Arial,sans-serif;color:#0f172a;max-width:640px">
  <p style="font-size:15px">{n} {'edital relevante apareceu' if n == 1 else 'editais relevantes apareceram'} no radar:</p>
  {''.join(itens_html)}
  {rodape_html}
</body></html>""", subtype="html")

with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as smtp:
    # login() tenta outro método quando a senha é recusada e o Gmail derruba a conexão,
    # escondendo o erro real (535); autenticar só com PLAIN mostra a mensagem correta
    smtp.ehlo()
    smtp.user, smtp.password = usuario, senha
    smtp.auth("PLAIN", smtp.auth_plain)
    smtp.send_message(msg)
print(f"E-mail enviado para {destino}: {assunto}")
