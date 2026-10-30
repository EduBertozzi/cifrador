//go:build windows

package main

import (
	"syscall"
	"unsafe"
)

// espaço livre no disco onde está a pasta, em GB
func freeGB(path string) float64 {
	kernel := syscall.NewLazyDLL("kernel32.dll")
	proc := kernel.NewProc("GetDiskFreeSpaceExW")
	pointer, err := syscall.UTF16PtrFromString(path)
	if err != nil {
		return 0
	}
	var free, total, totalFree uint64
	result, _, _ := proc.Call(
		uintptr(unsafe.Pointer(pointer)),
		uintptr(unsafe.Pointer(&free)),
		uintptr(unsafe.Pointer(&total)),
		uintptr(unsafe.Pointer(&totalFree)),
	)
	if result == 0 {
		return 0
	}
	return float64(free) / 1024 / 1024 / 1024
}

// console do Windows em UTF-8, senão "instalação" vira "instalaÃ§Ã£o"
func init() {
	kernel := syscall.NewLazyDLL("kernel32.dll")
	kernel.NewProc("SetConsoleOutputCP").Call(65001)
	kernel.NewProc("SetConsoleCP").Call(65001)
}
