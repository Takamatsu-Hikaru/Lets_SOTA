//go:build windows

package main

import (
	"os/exec"
	"syscall"
)

func hiddenProc() *syscall.SysProcAttr {
	return &syscall.SysProcAttr{HideWindow: true}
}

// 保留兼容：build.bat 中直接用 go build，CREATE_NO_WINDOW 由 SysProcAttr 控制
var _ = exec.Command
