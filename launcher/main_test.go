package main

import (
	"archive/zip"
	"bytes"
	"crypto/rand"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync/atomic"
	"testing"
)

// servidor que corta a conexão a cada 300 KB, igual internet ruim
func flakyServer(t *testing.T, payload []byte, cuts *int32) *httptest.Server {
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := 0
		if rng := r.Header.Get("Range"); rng != "" {
			start, _ = strconv.Atoi(strings.TrimSuffix(strings.TrimPrefix(rng, "bytes="), "-"))
			w.Header().Set("Content-Range", fmt.Sprintf("bytes %d-%d/%d", start, len(payload)-1, len(payload)))
			w.Header().Set("Content-Length", strconv.Itoa(len(payload)-start))
			w.WriteHeader(http.StatusPartialContent)
		} else {
			w.Header().Set("Content-Length", strconv.Itoa(len(payload)))
			w.WriteHeader(http.StatusOK)
		}
		end := start + 300*1024
		if end >= len(payload) {
			w.Write(payload[start:])
			return
		}
		w.Write(payload[start:end])
		atomic.AddInt32(cuts, 1)
		// derruba a conexão no meio
		hj, ok := w.(http.Hijacker)
		if !ok {
			t.Fatal("sem hijack")
		}
		w.(http.Flusher).Flush()
		conn, _, _ := hj.Hijack()
		conn.Close()
	}))
}

func TestDownloadResumesAfterDrops(t *testing.T) {
	payload := make([]byte, 2*1024*1024+123)
	rand.Read(payload)
	var cuts int32
	server := flakyServer(t, payload, &cuts)
	defer server.Close()

	dir := t.TempDir()
	target := filepath.Join(dir, "torch.whl")
	if err := tryDownload(server.URL+"/torch.whl", target, true); err != nil {
		t.Fatal(err)
	}
	got, _ := os.ReadFile(target)
	if !bytes.Equal(got, payload) {
		t.Fatalf("arquivo diferente: %d vs %d bytes", len(got), len(payload))
	}
	if cuts < 5 {
		t.Fatalf("esperava várias quedas, teve %d", cuts)
	}
	if exists(target + ".parcial") {
		t.Fatal("sobrou arquivo parcial")
	}
	t.Logf("baixou %d bytes inteiros depois de %d quedas", len(payload), cuts)
}

func TestDownloadContinuesFromPartialOnDisk(t *testing.T) {
	// simula: fechou o programa no meio, abriu de novo
	payload := make([]byte, 900*1024)
	rand.Read(payload)
	var cuts int32
	server := flakyServer(t, payload, &cuts)
	defer server.Close()
	dir := t.TempDir()
	target := filepath.Join(dir, "x.bin")
	os.WriteFile(target+".parcial", payload[:500*1024], 0o644)
	if err := tryDownload(server.URL, target, true); err != nil {
		t.Fatal(err)
	}
	got, _ := os.ReadFile(target)
	if !bytes.Equal(got, payload) {
		t.Fatal("não continuou certo do parcial")
	}
}

func TestUnzipStripAndChanges(t *testing.T) {
	dir := t.TempDir()
	zipPath := filepath.Join(dir, "repo.zip")
	file, _ := os.Create(zipPath)
	writer := zip.NewWriter(file)
	for name, body := range map[string]string{
		"cifrador-main/":                   "",
		"cifrador-main/requirements.txt":   "torch\n",
		"cifrador-main/cifrador/server.py": "print('oi')\n",
		"cifrador-main/../../fora.txt":     "ataque",
	} {
		w, _ := writer.Create(name)
		w.Write([]byte(body))
	}
	writer.Close()
	file.Close()

	target := filepath.Join(dir, "app")
	if n := unzip(zipPath, target, "strip"); n != 2 {
		t.Fatalf("esperava 2 arquivos, veio %d", n)
	}
	if !exists(filepath.Join(target, "cifrador", "server.py")) {
		t.Fatal("não extraiu")
	}
	if exists(filepath.Join(dir, "..", "fora.txt")) {
		t.Fatal("escapou da pasta")
	}
	if n := unzip(zipPath, target, "strip"); n != 0 {
		t.Fatalf("segunda vez devia mudar 0, mudou %d", n)
	}
}

func TestRealDownloads(t *testing.T) {
	if os.Getenv("REDE") == "" {
		t.Skip("REDE=1 pra testar downloads reais")
	}
	dados = t.TempDir()
	repo := filepath.Join(dados, "app.zip")
	if err := tryDownload(repoZip, repo, false); err != nil {
		t.Fatal("repo:", err)
	}
	n := unzip(repo, filepath.Join(dados, "app"), "strip")
	if !exists(filepath.Join(dados, "app", "requirements.txt")) || !exists(filepath.Join(dados, "app", "cifrador", "pipeline.py")) {
		t.Fatal("repo sem arquivos")
	}
	t.Logf("repo ok, %d arquivos", n)

	uv := filepath.Join(dados, "uv.zip")
	if err := tryDownload(uvZip, uv, true); err != nil {
		t.Fatal("uv:", err)
	}
	unzip(uv, filepath.Join(dados, "uv"), "")
	if !exists(filepath.Join(dados, "uv", "uv.exe")) {
		t.Fatal("zip do uv não tem uv.exe")
	}
	t.Log("uv ok")
}
