# Job Apply Assistant — Instalação macOS (Guilherme) v1.0.12

Este guia é para instalar a **versão 1.0.12** no Mac do Guilherme.  
Nesta build, **perfil, currículo, experiências e chave Groq** são aplicados automaticamente na **primeira abertura**.

> **Já tem o app instalado?** Abra **Configurações → Updates → Check for updates → Update now**.  
> O app **reinicia sozinho**, instala em **Aplicativos**, cria atalho na **Área de Trabalho**, e **não apaga** `~/.autoapply/` (incluindo vagas importadas).

> **Importante:** no Mac, apps baixados da internet costumam ficar bloqueados.  
> Se o duplo clique não abrir, use os comandos do Terminal abaixo (é o método mais confiável).

---

## 1. Download

Baixe o zip **mac-arm64** (Mac com chip M1/M2/M3/M4):

https://github.com/Krassusky/gui-job-aplication1/releases/tag/v1.0.12

Arquivo esperado:

```text
JobApplyAssistant-1.0.12-mac-arm64.zip
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
unzip -o JobApplyAssistant-1.0.12-mac-arm64.zip -d JobApplyAssistant-1.0.12
cd JobApplyAssistant-1.0.12
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
| Vagas / perfil compartilhado do PC de casa | **Não** — sync manual abaixo |

---

## 8. Configuração no app (depois de abrir)

### 8.0 O que **não** é a senha do Mac app

| Onde | Para quê | Credencial |
|------|----------|------------|
| **Mac app** → Settings → Sync token | Importar vagas e puxar perfil/busca | **Token de sync** (peça ao Luis) — **não** é senha de usuário |
| **Navegador** → https://jobs.krassusky.com/dashboard | Ver/editar busca no servidor (opcional) | Login **guilherme** + senha (Luis envia **à parte**) |
| **Mac app** → Platform Login → LinkedIn | Sessão do LinkedIn no Safari do app | E-mail/senha do **LinkedIn** |

O campo **Sync token** no Mac **não** aceita a senha do dashboard. São coisas diferentes.

### 8.1 LinkedIn (uma vez)

1. **Settings** → **Platform Login** → **LinkedIn**
2. Faça login com **e-mail e senha** do LinkedIn  
3. **Não use** “Entrar com Google” (bloqueado no navegador do app)

### 8.2 Sync com o servidor de casa (obrigatório)

Peça ao **Luis**:

- **URL:** `https://jobs.krassusky.com`
- **Sync token:** o mesmo valor de `AUTOAPPLY_SYNC_TOKEN` / arquivo `~/.autoapply/.sync_token` no servidor (Luis envia por canal privado — **não** está neste guia)

No app:

1. **Settings** → **Import Jobs from Home Server**
2. Cole:
   - **Sync server URL:** `https://jobs.krassusky.com`
   - **Sync token:** o token que o Luis enviou
3. **Test connection** (deve dar OK)
4. **Import pending jobs** — traz vagas descobertas pelo caçador
5. **Pull shared profile & search** — copia perfil + filtros de busca do servidor para o Mac (mantém chave Groq e caminhos locais de currículo)
6. Abra **Candidaturas** — vagas importadas aparecem com status **Discovered**
7. Clique numa vaga → **Generate Resume & Cover Letter** → **Apply to This Job**
8. Quando a carta aparecer, revise e clique **Approve & Apply**

Durante import / generate / apply, o app mostra um **overlay de carregamento** — aguarde terminar.

### 8.3 Settings em cinza + botão **Edit**

Os campos de configuração ficam **somente leitura** (cinza) para evitar mudanças acidentais.

- Clique **Edit** (Editar) para alterar
- Clique **Done** (Concluir) / salve para voltar ao modo bloqueado
- Os botões de sync (**Test**, **Import**, **Pull shared…**) continuam usáveis mesmo com settings bloqueados

### 8.4 Modo cliente neste Mac

Abas: **Candidaturas**, **Arquivos de experiência**, **Dados para candidaturas**, **Configurações**.  
(Guia, Painel, Análises, Biblioteca de currículos e preferências de busca/agenda ficam ocultos — a busca roda no servidor.)

Seus dados em `~/.autoapply/autoapply.db` **não são apagados** ao atualizar o app.

### 8.5 Dashboard web (opcional — não é o Mac app)

Se o Luis pedir para você ajustar filtros no servidor:

1. Abra https://jobs.krassusky.com/dashboard no navegador
2. Entre com o usuário **guilherme** e a senha que o Luis enviar **separadamente**
3. Isso **não** substitui o sync token no Mac

---

## 9. Atualizar (recomendado: na app)

1. Abra o app → **Configurações → Updates**
2. **Check for updates** → **Update now** (ou Download + Install and restart)
3. Se aparecer um banner no topo, use **Atualizar agora**
4. O app fecha, instala em **Aplicativos**, cria atalho na **Área de Trabalho** e reabre sozinho

Seus dados em `~/.autoapply/` **não são apagados** ao atualizar.

### Alternativa manual (zip)

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
| Import / pull falha | URL `https://jobs.krassusky.com` + **sync token** (não a senha do dashboard); confirme que o Job Hunter está ativo |
| Confundiu token com senha do site | Dashboard = usuário/senha; Mac = sync token. Peça de novo ao Luis se precisar |
| Settings cinza / não edita | Clique **Edit** no topo das configurações |
| Groq / IA não responde | Settings → AI Provider → validar Groq |
| LinkedIn não conecta | E-mail/senha, não Google; tente de novo no login do app |

---

## 12. Suporte

- Releases: https://github.com/Krassusky/gui-job-aplication1/releases  
- Sync API (Guilherme): https://jobs.krassusky.com  
- Dashboard do caçador (login separado): https://jobs.krassusky.com/dashboard  
