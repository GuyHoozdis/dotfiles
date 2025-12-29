" vim fdm=marker

" Settings ------------------------------------------------------------

" Preamble {{{

" Make vim more useful {{{
set nocompatible
"}}}

"Syntax highlighting {{{
set t_Co=256
set background=dark
syntax on
colorscheme torte
" }}}

" Mapleader {{{
let mapleader=","
"}}}

" Local directories {{{
"set backupdir=~/.vim/backups
"set directory=~/.vim/swaps
"set undodir=~/.vim/undo
" }}}


set tabstop=4
set softtabstop=4
set shiftwidth=4
set expandtab

set number
set nowrap


" Sudo write (,W) {{{
noremap <leader>W :w !sudo tee %<CR>
" }}}
