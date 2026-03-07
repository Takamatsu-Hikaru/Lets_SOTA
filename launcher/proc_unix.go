//go:build !windows

package main

import "syscall"

func hiddenProc() *syscall.SysProcAttr {
	return nil
}
