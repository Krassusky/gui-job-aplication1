# Job Apply Assistant — Instalação macOS (Guilherme) v1.0.9

Este guia é para instalar a **versão 1.0.9** no Mac do Guilherme.  
Nesta build, **perfil, currículo, experiências e chave Groq** são aplicados automaticamente na **primeira abertura**.

> **Importante:** no Mac, apps baixados da internet costumam ficar bloqueados.  
> Se o duplo clique não abrir, use os comandos do Terminal abaixo (é o método mais confiável).

---

## 1. Download

Baixe o zip **mac-arm64** (Mac com chip M1/M2/M3/M4):

https://github.com/Krassusky/gui-job-aplication1/releases/tag/v1.0.9

Arquivo esperado:

```text
JobApplyAssistant-1.0.9-mac-arm64.zip
```

---

## 2. Abrir o Terminal

- **Spotlight:** `Cmd + Espaço` → digite `Terminal` → Enter  
- Ou: Aplicativos → Utilitários → Terminal

---

## 3. Extrair o zip (comandos)

Copie e cole **linha por linha** (ajuste o caminho se o zip estiver em outra pasta):

```bash
cd ~/Downloads
unzip -o JobApplyAssistant-1.0.9-mac-arm64.zip -d JobApplyAssistant-1.0.9
cd JobApplyAssistant-1.0.9
ls -la
```

Você deve ver:

- `JobApplyAssistant.app`
- `Desbloquear arquivos.command`
- `Install JobApply Assistant.command`
- `COMECE-AQUI.txt`
- `INSTALACAO-MAC-GUILHERME.md` (este guia)

---

## 4. Remover bloqueio de segurança (quarentena)

```bash
xattr -dr com.apple.quarantine .
xattr -dr com.apple.quarantine JobApplyAssistant.app
```

Se pedir senha do Mac, digite a senha do usuário (não aparece enquanto digita — é normal).

---

## 5. Instalar em Aplicativos

### Opção A — script (duplo clique)

Duplo clique em: **Install JobApply Assistant.command**

### Opção B — Terminal (recomendado)

```bash
# Remover versão antiga, se existir
rm -rf /Applications/JobApplyAssistant.app

# Copiar nova versão
cp -R JobApplyAssistant.app /Applications/

# Remover quarentena de novo após copiar
xattr -dr com.apple.quarantine /Applications/JobApplyAssistant.app

# Dar permissão de execução ao binário interno
chmod +x /Applications/JobApplyAssistant.app/Contents/MacOS/JobApplyAssistant
```

---

## 6. Primeira abertura (use o Terminal)

**Não confie só no duplo clique na primeira vez.** Abra assim:

```bash
open /Applications/JobApplyAssistant.app
```

Se ainda não abrir, rode o executável direto (mostra erros no Terminal):

```bash
/Applications/JobApplyAssistant.app/Contents/MacOS/JobApplyAssistant
```

### Se o Mac disser que o app é de um desenvolvedor não identificado

1. **Preferência:** System Settings → Privacy & Security → abra mesmo assim (**Open Anyway**), **ou**
2. Botão direito em `JobApplyAssistant.app` → **Abrir** → **Abrir** (só uma vez)

---

## 7. O que acontece na primeira abertura

O app grava automaticamente em:

```text
/Users/SEU_USUARIO/.autoapply/
```

Inclui:

| Item | Preenchido? |
|------|-------------|
| Nome, e-mail, telefone, LinkedIn | Sim |
| Currículo `default_resume.docx` | Sim |
| Arquivos de experiência (IA) | Sim |
| Chave Groq | Sim (nesta build) |
| Login LinkedIn (sessão) | **Não** — passo manual abaixo |
| Vagas do PC de casa | **Não** — import manual abaixo |

---

## 8. Configuração única no app (depois de abrir)

### 8.1 LinkedIn (uma vez)

1. **Settings** → **Platform Login** → **LinkedIn**
2. Faça login com **e-mail e senha** do LinkedIn  
3. **Não use** “Entrar com Google” (bloqueado no navegador do app)

### 8.2 Importar vagas do PC de casa

Peça ao Krassusky:

- **URL:** `https://jobs.krassusky.com`  
  (Cloudflare Tunnel — funciona de qualquer rede, sem mesma Wi‑Fi)
- **Token:** arquivo `SYNC-TOKEN-FOR-GUILHERME.txt` no PC Windows

No app:

1. **Settings** → **Import Jobs from Home Server**
2. Cole URL e token
3. **Test connection**
4. **Import pending jobs**
5. Abra **Candidaturas** (aba principal neste Mac) — as vagas importadas aparecem com status **Discovered**
6. Clique numa vaga → veja JD / URL → **Generate Resume & Cover Letter** → **Apply to This Job**
7. Quando a carta aparecer, revise e clique **Approve & Apply**

Abas neste Mac (modo cliente): **Candidaturas**, **Arquivos de experiência**, **Dados para candidaturas**, **Configurações**.  
(Guia, Painel, Análises e Biblioteca de currículos ficam ocultos — a busca de vagas roda no PC Windows.)

Seus dados em `~/.autoapply/autoapply.db` **não são apagados** ao atualizar o app.

---

## 9. Atualizar no futuro (v1.0.10+)

```bash
cd ~/Downloads
unzip -o JobApplyAssistant-NOVA-VERSAO-mac-arm64.zip -d JobApplyAssistant-novo
cd JobApplyAssistant-novo
xattr -dr com.apple.quarantine .
rm -rf /Applications/JobApplyAssistant.app
cp -R JobApplyAssistant.app /Applications/
xattr -dr com.apple.quarantine /Applications/JobApplyAssistant.app
chmod +x /Applications/JobApplyAssistant.app/Contents/MacOS/JobApplyAssistant
open /Applications/JobApplyAssistant.app
```

Seus dados em `~/.autoapply/` **não são apagados** ao atualizar.

---

## 10. Verificar se o preset foi aplicado

No Terminal:

```bash
test -f ~/.autoapply/config.json && echo "Config OK"
test -f ~/.autoapply/default_resume.docx && echo "Resume OK"
test -f ~/.autoapply/.preset-guilherme-menegatti-v1 && echo "Preset Guilherme OK"
```

Testar API (qualquer rede, via Cloudflare):

```bash
curl -s https://jobs.krassusky.com/api/sync/health
```

Resposta esperada: `{"status":"ok"}`

---

## 11. Problemas comuns

| Problema | Solução |
|----------|---------|
| App não abre no duplo clique | Use `open /Applications/JobApplyAssistant.app` ou o binário direto (secção 6) |
| “App danificado” / quarentena | Rode `xattr -dr com.apple.quarantine` de novo |
| Import falha | URL `https://jobs.krassusky.com` + token; confirme que o tunnel Cloudflare e o Job Hunter estão ativos |
| Groq / IA não responde | Settings → AI Provider → validar Groq |
| LinkedIn não conecta | E-mail/senha, não Google; tente de novo no login do app |

---

## 12. Suporte

- Releases: https://github.com/Krassusky/gui-job-aplication1/releases  
- Sync API (Guilherme): https://jobs.krassusky.com  
- Dashboard do caçador (só no PC de casa / LAN): http://127.0.0.1:8765/dashboard  
