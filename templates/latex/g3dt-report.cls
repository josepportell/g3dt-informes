% G3DT Geotechnical Report Class
% Based on PDF analysis of original reports (2026-01-04)
% Requires XeLaTeX for custom font support

\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{g3dt-report}[2026/01/04 G3DT Geotechnical Report Class]

% Base class
\LoadClass[a4paper,10pt]{article}

% ============================================================================
% PACKAGES
% ============================================================================

\RequirePackage{fontspec}           % Custom fonts (XeLaTeX)
\RequirePackage{xcolor}             % Colors
\RequirePackage{geometry}           % Page layout
\RequirePackage{fancyhdr}           % Headers/footers
\RequirePackage{titlesec}           % Section formatting
\RequirePackage{tabularx}           % Tables
\RequirePackage{booktabs}           % Professional tables
\RequirePackage{graphicx}           % Images
\RequirePackage{float}              % Figure placement
\RequirePackage{caption}            % Caption formatting
\RequirePackage{hyperref}           % Links
\RequirePackage{lastpage}           % Last page number
\RequirePackage{enumitem}           % List formatting
\RequirePackage{tocloft}            % TOC formatting
\RequirePackage{tikz}               % Graphics (for page number box)
\RequirePackage{eso-pic}            % Background elements
\RequirePackage{setspace}           % Line spacing
\RequirePackage{parskip}            % Paragraph spacing

% ============================================================================
% COLORS (from PDF analysis)
% ============================================================================

\definecolor{g3green-headings}{HTML}{003300}   % Section headings - very dark green
\definecolor{g3green-links}{HTML}{008000}      % Website links - pure green
\definecolor{g3green-box}{HTML}{4A7C59}        % Page number box
\definecolor{g3green-light}{HTML}{8FBC8F}      % Light green accents
\definecolor{g3gray-table}{HTML}{F5F5F5}       % Table alternating rows

% ============================================================================
% FONTS (Swiss721BT-LightExtended extracted from PDF)
% ============================================================================

% Main font - Try to load Swiss721BT-LightExtended (extracted subset from PDF)
% Note: This is a SUBSET font - fallback to Liberation Sans for full coverage
\IfFontExistsTF{Liberation Sans}{
    \setmainfont{Liberation Sans}
}{
    \setmainfont{DejaVu Sans}
}

% Try to load the extracted G3 font for special use
\newfontfamily\gthreefont{Swiss721BT-LightExtended}[
    Path = fonts/,
    Extension = .ttf,
    UprightFont = *,
    ItalicFont = *,
    BoldFont = *,
    BoldItalicFont = *,
]

% Sans-serif for headers/footers
\setsansfont{Liberation Sans}

% Define command to use G3 font for body text
\newcommand{\gthreetext}[1]{{\gthreefont #1}}

% ============================================================================
% PAGE LAYOUT (from PDF: 595 x 842 points = A4)
% ============================================================================

\geometry{
    a4paper,
    top=2.5cm,
    bottom=2.0cm,
    left=2.5cm,
    right=2.5cm,
    headheight=1.5cm,
    headsep=0.5cm,
    footskip=1.0cm,
}

% Line spacing (1.15)
\setstretch{1.15}

% Justified text
\setlength{\parindent}{0pt}
\setlength{\parskip}{6pt}

% ============================================================================
% SECTION FORMATTING (from PDF analysis)
% ============================================================================

% H1: 12pt dark green (#003300)
\titleformat{\section}
    {\normalfont\fontsize{12}{14}\selectfont\color{g3green-headings}}
    {\thesection.}
    {0.5em}
    {}

\titlespacing*{\section}{0pt}{18pt}{12pt}

% H2: 11pt dark green (#003300)
\titleformat{\subsection}
    {\normalfont\fontsize{11}{13}\selectfont\color{g3green-headings}}
    {\thesubsection.}
    {0.5em}
    {}

\titlespacing*{\subsection}{0pt}{12pt}{6pt}

% H3: 10pt italic black
\titleformat{\subsubsection}
    {\normalfont\fontsize{10}{12}\selectfont\itshape}
    {\thesubsubsection.}
    {0.5em}
    {}

\titlespacing*{\subsubsection}{0pt}{6pt}{3pt}

% ============================================================================
% HEADERS AND FOOTERS
% ============================================================================

\pagestyle{fancy}
\fancyhf{}

% Header: Logo | Title | Page number in green box
\fancyhead[L]{%
    \raisebox{-0.3\height}{\includegraphics[height=1cm]{assets/g3-logo-circular.png}}%
}
\fancyhead[C]{%
    \fontsize{9}{11}\selectfont\g3doctitle%
}
\fancyhead[R]{%
    \tikz[baseline=(num.base)]{
        \node[fill=g3green-box, text=white, font=\bfseries\fontsize{10}{12}\selectfont,
              inner sep=3pt, rounded corners=2pt] (num) {\thepage};
    }%
}

% Footer: Company | Website | Email
\fancyfoot[L]{%
    \fontsize{9}{11}\selectfont G3 DT, S.L.%
}
\fancyfoot[C]{%
    \fontsize{9}{11}\selectfont\color{g3green-links}\href{http://www.g3dt.com}{www.g3dt.com}%
}
\fancyfoot[R]{%
    \fontsize{9}{11}\selectfont g3@g3dt.com%
}

% Header/footer lines
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}

% Plain style for cover page (no header/footer)
\fancypagestyle{plain}{
    \fancyhf{}
    \renewcommand{\headrulewidth}{0pt}
    \renewcommand{\footrulewidth}{0pt}
}

% ============================================================================
% TABLE FORMATTING
% ============================================================================

% Table header style: 9pt bold white on green
\newcommand{\tableheader}[1]{%
    \cellcolor{g3green-headings}\textcolor{white}{\textbf{#1}}%
}

% Alternating row colors
\rowcolors{2}{white}{g3gray-table}

% ============================================================================
% CAPTION FORMATTING
% ============================================================================

\captionsetup{
    font={small},
    labelfont={bf},
    format=plain,
    justification=centering,
    skip=6pt,
}

% ============================================================================
% TOC FORMATTING
% ============================================================================

\renewcommand{\cftsecleader}{\cftdotfill{\cftdotsep}}
\renewcommand{\cftsubsecleader}{\cftdotfill{\cftdotsep}}
\setlength{\cftbeforesecskip}{3pt}

% ============================================================================
% CUSTOM COMMANDS
% ============================================================================

% Document title (for header)
\newcommand{\g3doctitle}{}
\newcommand{\setg3doctitle}[1]{\renewcommand{\g3doctitle}{#1}}

% Metadata block (for cover page)
\newcommand{\g3metadata}[4]{%
    \begin{tabular}{@{}ll@{}}
        \textbf{CLIENT:} & #1 \\[3pt]
        \textbf{EXPEDIENT:} & #2 \\[3pt]
        \textbf{DATA:} & #3 \\[3pt]
        \textbf{OBRA:} & \parbox[t]{10cm}{#4} \\
    \end{tabular}%
}

% Cover page command
\newcommand{\makecover}[5]{%
    % #1 = client, #2 = expedient, #3 = date, #4 = project description, #5 = location
    \thispagestyle{plain}
    \setg3doctitle{#2/Estudi geològic – geotècnic\_#5}

    % Top: Banner
    \begin{center}
        \includegraphics[width=12cm]{assets/25-anys-banner.png}
    \end{center}

    \vfill

    % Watermark G3
    \begin{flushright}
        \includegraphics[width=8cm]{assets/g3-watermark.png}
    \end{flushright}

    \vspace{2cm}

    % Metadata block
    \g3metadata{#1}{#2}{#3}{#4}

    \newpage
}

% Signature block
\newcommand{\signaturepage}[3]{%
    % #1 = location, #2 = date, #3 = signers (comma separated)
    \vfill
    \begin{center}
        #1, #2

        \vspace{2cm}

        % Signatures would go here
        \includegraphics[height=2cm]{assets/company-stamp.png}

        \vspace{1cm}

        #3
    \end{center}
    \newpage
}

% ============================================================================
% HYPERREF SETUP
% ============================================================================

\hypersetup{
    colorlinks=true,
    linkcolor=black,
    urlcolor=g3green-links,
    citecolor=black,
}

% ============================================================================
% END OF CLASS
% ============================================================================

\endinput
