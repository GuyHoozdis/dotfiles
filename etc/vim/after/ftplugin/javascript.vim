" https://github.com/ajh17/Spacegray.vim
"
colorscheme spacegray

let g:spacegray_underline_search = 1
let g:spacegray_use_italics = 1

" The highlighting for matching parens under the spacegray plugin is hard to
" see.  I want to find something that is easier to see.
"
" These are the settings used by other plugins.
"
" The solarized plugin:
"   hi MatchParen   ctermbg=NONE ctermfg=11 guibg=NONE guifg=#E5C078
"                   cterm=bold gui=bold
"
" The spacegray plugin:
" hi MatchParen term=bold cterm=bold ctermfg=1 ctermbg=10 gui=bold
"               guifg=#E5C078 guibg=DarkCyan
"
" ------------------------------------------------------------------------------
" This will color the matching paren an obvious color, but not get gaudy with
" the background.

hi MatchParen   term=bold cterm=bold ctermfg=1 ctermbg=NONE guibg=DarkCyan
