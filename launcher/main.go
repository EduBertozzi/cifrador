// Cifrador.exe: instala tudo na pasta onde ele está e abre o app.
//
// Nunca apaga nada. Se a internet cair ou fechar no meio, na próxima vez continua de onde parou.
// Nada vai pro disco C: (temporários, cache e modelos ficam em "Cifrador-dados", do lado do .exe).
package main

import (
	"archive/zip"
	"bufio"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

const (
	repoZip   = "https://github.com/EduBertozzi/cifrador/archive/refs/heads/main.zip"
	uvZip     = "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip"
	ffmpegZip = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
	pyVersion = "3.12"
	pyTag     = "cp312"
	torchVer  = "2.14.0"
	minFreeGB = 8
)

var (
	base  string // pasta onde está o .exe
	dados string // base\Cifrador-dados
	env   []string
)

func main() {
	exe, err := os.Executable()
	if err != nil {
		fail("não achei a pasta do programa", err)
	}
	base = filepath.Dir(exe)
	dados = filepath.Join(base, "Cifrador-dados")

	fmt.Println()
	fmt.Println("  ==========================================")
	fmt.Println("   CIFRADOR")
	fmt.Println("  ==========================================")
	fmt.Println()
	fmt.Println("  Pasta:", dados)
	fmt.Println()

	must(os.MkdirAll(dados, 0o755))
	setupEnv()

	firstTime := !exists(mark("pronto"))
	if firstTime {
		fmt.Println("  Primeira vez: vou instalar tudo AQUI nessa pasta.")
		fmt.Println("  Leva uns 10 a 20 minutos. Se cair a internet ou fechar,")
		fmt.Println("  é só abrir de novo que ele continua de onde parou.")
		fmt.Println()
		checkDisk()
	}

	step(1, "ffmpeg (leitor de áudio)", installFFmpeg)
	step(2, "uv (instalador de Python)", installUV)
	step(3, "Python "+pyVersion, installPython)
	step(4, "PyTorch (IA)", installTorch)
	updated := updateApp()
	step(6, "bibliotecas", func() { installLibs(updated) })

	if firstTime {
		touch(mark("pronto"))
		fmt.Println()
		fmt.Println("  Instalado! Da próxima vez ele já abre direto.")
	}

	fmt.Println()
	fmt.Println("  Abrindo no navegador... (não feche esta janela enquanto usa)")
	fmt.Println()
	run(filepath.Join(dados, "venv", "Scripts", "python.exe"), []string{"-m", "cifrador"}, filepath.Join(dados, "app"))
	pause()
}

// ---------- passos ----------

func step(n int, name string, fn func()) {
	fmt.Printf("  [%d/6] %s\n", n, name)
	fn()
}

func installFFmpeg() {
	bin := filepath.Join(dados, "ffmpeg", "bin")
	if exists(filepath.Join(bin, "ffmpeg.exe")) {
		ok("ok")
		return
	}
	if _, err := exec.LookPath("ffmpeg"); err == nil {
		ok("já tinha no computador")
		return
	}
	zipPath := filepath.Join(dados, "temp", "ffmpeg.zip")
	download(ffmpegZip, zipPath)
	// o zip vem com uma pasta tipo "ffmpeg-7.1-essentials_build/bin/ffmpeg.exe"
	tmp := filepath.Join(dados, "temp", "ffmpeg")
	unzip(zipPath, tmp, "")
	entries, _ := os.ReadDir(tmp)
	for _, entry := range entries {
		candidate := filepath.Join(tmp, entry.Name(), "bin")
		if exists(filepath.Join(candidate, "ffmpeg.exe")) {
			must(os.MkdirAll(filepath.Dir(bin), 0o755))
			must(os.Rename(candidate, bin))
		}
	}
	os.RemoveAll(tmp)
	os.Remove(zipPath)
	if !exists(filepath.Join(bin, "ffmpeg.exe")) {
		fail("ffmpeg não instalou", nil)
	}
	ok("instalado")
}

func uvExe() string { return filepath.Join(dados, "uv", "uv.exe") }

func installUV() {
	if exists(uvExe()) {
		ok("ok")
		return
	}
	zipPath := filepath.Join(dados, "temp", "uv.zip")
	download(uvZip, zipPath)
	unzip(zipPath, filepath.Join(dados, "uv"), "")
	os.Remove(zipPath)
	if !exists(uvExe()) {
		fail("uv não instalou", nil)
	}
	ok("instalado")
}

func installPython() {
	python := filepath.Join(dados, "venv", "Scripts", "python.exe")
	if exists(mark("python")) && exists(python) {
		ok("ok")
		return
	}
	run(uvExe(), []string{"python", "install", pyVersion}, dados)
	run(uvExe(), []string{"venv", filepath.Join(dados, "venv"), "--python", pyVersion, "--allow-existing"}, dados)
	if !exists(python) {
		fail("Python não instalou", nil)
	}
	touch(mark("python"))
	ok("instalado")
}

func installTorch() {
	if exists(mark("torch")) {
		ok("ok")
		return
	}
	// placa NVIDIA: CUDA 12.6 (última que ainda suporta GTX 10xx). Sem placa: só CPU
	flavor := "cpu"
	if hasNvidia() {
		flavor = "cu126"
	}
	name := fmt.Sprintf("torch-%s+%s-%s-%s-win_amd64.whl", torchVer, flavor, pyTag, pyTag)
	url := fmt.Sprintf("https://download.pytorch.org/whl/%s/torch-%s%%2B%s-%s-%s-win_amd64.whl", flavor, torchVer, flavor, pyTag, pyTag)
	if flavor == "cu126" {
		fmt.Println("        placa NVIDIA encontrada: versão com CUDA (~2,6 GB)")
	} else {
		fmt.Println("        sem placa NVIDIA: versão CPU (~200 MB)")
	}
	wheel := filepath.Join(dados, "temp", name)
	download(url, wheel)
	run(uvExe(), []string{"pip", "install", "--python", venvPython(), wheel}, dados)
	os.Remove(wheel)
	touch(mark("torch"))
	ok("instalado")
}

// baixa o código mais novo do GitHub. Devolve true se mudou algo
func updateApp() bool {
	fmt.Println("  [5/6] código do Cifrador")
	zipPath := filepath.Join(dados, "temp", "app.zip")
	os.Remove(zipPath)
	if err := tryDownload(repoZip, zipPath, false); err != nil {
		if exists(filepath.Join(dados, "app", "cifrador")) {
			ok("sem internet agora, usando a versão que já tem")
			return false
		}
		fail("não consegui baixar o código do GitHub", err)
	}
	changed := unzip(zipPath, filepath.Join(dados, "app"), "strip")
	os.Remove(zipPath)
	if changed > 0 {
		ok(fmt.Sprintf("atualizado (%d arquivos)", changed))
		// apaga cache velho do Python
		filepath.Walk(filepath.Join(dados, "app"), func(path string, info os.FileInfo, err error) error {
			if err == nil && info.IsDir() && info.Name() == "__pycache__" {
				os.RemoveAll(path)
				return filepath.SkipDir
			}
			return nil
		})
		return true
	}
	ok("já é a versão mais nova")
	return false
}

func installLibs(appChanged bool) {
	req := filepath.Join(dados, "app", "requirements.txt")
	sum := fileHash(req)
	if exists(mark("libs")) {
		old, _ := os.ReadFile(mark("libs"))
		if strings.TrimSpace(string(old)) == sum {
			ok("ok")
			return
		}
	}
	run(uvExe(), []string{"pip", "install", "--python", venvPython(), "-r", req}, dados)
	must(os.WriteFile(mark("libs"), []byte(sum), 0o644))
	ok("instalado")
}

// ---------- ambiente ----------

func venvPython() string { return filepath.Join(dados, "venv", "Scripts", "python.exe") }

func setupEnv() {
	temp := filepath.Join(dados, "temp")
	modelos := filepath.Join(dados, "modelos")
	must(os.MkdirAll(temp, 0o755))
	must(os.MkdirAll(modelos, 0o755))
	extra := map[string]string{
		"TEMP":                  temp,
		"TMP":                   temp,
		"UV_CACHE_DIR":          filepath.Join(dados, "cache"),
		"UV_PYTHON_INSTALL_DIR": filepath.Join(dados, "python"),
		"UV_PYTHON_PREFERENCE":  "only-managed",
		"UV_LINK_MODE":          "copy",
		"UV_HTTP_TIMEOUT":       "300",
		"PIP_CACHE_DIR":         filepath.Join(dados, "cache", "pip"),
		"HF_HOME":               filepath.Join(modelos, "huggingface"),
		"TORCH_HOME":            filepath.Join(modelos, "torch"),
		"XDG_CACHE_HOME":        modelos,
		"CIFRADOR_MUSICAS":      filepath.Join(dados, "musicas"),
		"PYTHONUTF8":            "1",
	}
	path := filepath.Join(dados, "ffmpeg", "bin") + string(os.PathListSeparator) + os.Getenv("PATH")
	for _, item := range os.Environ() {
		key := strings.SplitN(item, "=", 2)[0]
		if _, replaced := extra[key]; replaced || strings.EqualFold(key, "PATH") {
			continue
		}
		env = append(env, item)
	}
	for key, value := range extra {
		env = append(env, key+"="+value)
	}
	env = append(env, "PATH="+path)
}

func hasNvidia() bool {
	if _, err := exec.LookPath("nvidia-smi"); err == nil {
		return true
	}
	return exists(`C:\Windows\System32\nvidia-smi.exe`)
}

// ---------- download que aguenta internet caindo ----------

func download(url, target string) {
	if err := tryDownload(url, target, true); err != nil {
		fail("download falhou: "+url, err)
	}
}

func tryDownload(url, target string, resume bool) error {
	must(os.MkdirAll(filepath.Dir(target), 0o755))
	if exists(target) {
		return nil
	}
	part := target + ".parcial"
	client := &http.Client{Timeout: 0}
	var lastErr error
	for attempt := 1; attempt <= 60; attempt++ {
		var have int64
		if info, err := os.Stat(part); err == nil && resume {
			have = info.Size()
		}
		req, _ := http.NewRequest("GET", url, nil)
		req.Header.Set("User-Agent", "Cifrador")
		if have > 0 {
			req.Header.Set("Range", fmt.Sprintf("bytes=%d-", have))
		}
		resp, err := client.Do(req)
		if err != nil {
			lastErr = err
			retryWait(attempt, err)
			continue
		}
		if resp.StatusCode == http.StatusRequestedRangeNotSatisfiable {
			resp.Body.Close()
			break // já baixou tudo
		}
		if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusPartialContent {
			resp.Body.Close()
			lastErr = fmt.Errorf("HTTP %d", resp.StatusCode)
			if resp.StatusCode == 404 {
				return lastErr
			}
			retryWait(attempt, lastErr)
			continue
		}
		flags := os.O_CREATE | os.O_WRONLY
		if resp.StatusCode == http.StatusPartialContent {
			flags |= os.O_APPEND
		} else {
			flags |= os.O_TRUNC
			have = 0
		}
		file, err := os.OpenFile(part, flags, 0o644)
		if err != nil {
			resp.Body.Close()
			return err
		}
		total := have + resp.ContentLength
		counter := &progress{reader: resp.Body, done: have, total: total, last: time.Now()}
		_, err = io.Copy(file, counter)
		file.Close()
		resp.Body.Close()
		fmt.Print("\r                                                            \r")
		if err != nil {
			lastErr = err
			// avançou alguma coisa: não conta como tentativa perdida
			if counter.done > have {
				attempt = 0
			}
			retryWait(attempt, err)
			continue
		}
		lastErr = nil
		break
	}
	if lastErr != nil {
		return lastErr
	}
	return os.Rename(part, target)
}

func retryWait(attempt int, err error) {
	fmt.Printf("\r        a conexão caiu (%v). Continuando de onde parou...\n", shortErr(err))
	time.Sleep(time.Duration(max(1, min(attempt, 10))) * time.Second)
}

type progress struct {
	reader io.Reader
	done   int64
	total  int64
	last   time.Time
}

func (p *progress) Read(buf []byte) (int, error) {
	n, err := p.reader.Read(buf)
	p.done += int64(n)
	if time.Since(p.last) > 400*time.Millisecond {
		p.last = time.Now()
		if p.total > 0 {
			fmt.Printf("\r        baixando %.0f de %.0f MB (%d%%)   ", mb(p.done), mb(p.total), p.done*100/p.total)
		} else {
			fmt.Printf("\r        baixando %.0f MB   ", mb(p.done))
		}
	}
	return n, err
}

// ---------- zip ----------

// extrai o zip. mode "strip" tira a primeira pasta (zip do GitHub). Devolve quantos arquivos mudaram
func unzip(zipPath, target, mode string) int {
	reader, err := zip.OpenReader(zipPath)
	if err != nil {
		fail("arquivo baixado veio quebrado, abra de novo", err)
	}
	defer reader.Close()
	changed := 0
	for _, file := range reader.File {
		name := file.Name
		if mode == "strip" {
			parts := strings.SplitN(name, "/", 2)
			if len(parts) < 2 || parts[1] == "" {
				continue
			}
			name = parts[1]
		}
		dest := filepath.Join(target, filepath.FromSlash(name))
		if !strings.HasPrefix(dest, filepath.Clean(target)+string(os.PathSeparator)) {
			continue
		}
		if file.FileInfo().IsDir() {
			os.MkdirAll(dest, 0o755)
			continue
		}
		src, err := file.Open()
		if err != nil {
			continue
		}
		content, _ := io.ReadAll(src)
		src.Close()
		if old, err := os.ReadFile(dest); err == nil && string(old) == string(content) {
			continue
		}
		os.MkdirAll(filepath.Dir(dest), 0o755)
		must(os.WriteFile(dest, content, 0o644))
		changed++
	}
	return changed
}

// ---------- utilidades ----------

func run(program string, args []string, dir string) {
	cmd := exec.Command(program, args...)
	cmd.Dir = dir
	cmd.Env = env
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Stdin = os.Stdin
	if err := cmd.Run(); err != nil {
		fail("comando falhou: "+filepath.Base(program)+" "+strings.Join(args, " "), err)
	}
}

func mark(name string) string { return filepath.Join(dados, ".ok-"+name) }

func touch(path string) { must(os.WriteFile(path, []byte("ok"), 0o644)) }

func exists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

func fileHash(path string) string {
	content, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	sum := sha256.Sum256(content)
	return hex.EncodeToString(sum[:])
}

func checkDisk() {
	free := freeGB(dados)
	if free <= 0 {
		return
	}
	fmt.Printf("  Espaço livre nesse disco: %.1f GB\n\n", free)
	if free < minFreeGB {
		fmt.Printf("  ATENÇÃO: precisa de uns %d GB livres. Libere espaço ou\n", minFreeGB)
		fmt.Println("  mova o Cifrador.exe pra outro disco e abra de lá.")
		pause()
		os.Exit(1)
	}
}

func mb(bytes int64) float64 { return float64(bytes) / 1024 / 1024 }

func shortErr(err error) string {
	text := err.Error()
	if len(text) > 60 {
		return text[:60] + "..."
	}
	return text
}

func ok(text string) { fmt.Println("        " + text) }

func must(err error) {
	if err != nil {
		fail("erro", err)
	}
}

func fail(message string, err error) {
	fmt.Println()
	fmt.Println("  ==========================================")
	fmt.Println("   Deu erro:", message)
	if err != nil {
		fmt.Println("  ", err)
	}
	fmt.Println("   Nada foi apagado. Abra de novo pra continuar,")
	fmt.Println("   ou manda print dessa janela.")
	fmt.Println("  ==========================================")
	pause()
	os.Exit(1)
}

func pause() {
	fmt.Println()
	fmt.Print("  Aperte Enter pra fechar...")
	bufio.NewReader(os.Stdin).ReadString('\n')
}
