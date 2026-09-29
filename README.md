# CrossOver 오버워치 한국 서버 실행 오류 복구 가이드

이 패치는 macOS의 CrossOver에서 한국 오버워치가 시작 직후 종료되고 `E01300B0`이 기록되는 경우를 위한 것입니다. 검증한 환경은 Apple Silicon Mac에서 Rosetta로 x86_64 CrossOver 런타임을 실행한 경우입니다. 설치 프로그램은 필요한 Wine 파일과 아키텍처를 검사하고 인증서 체인 검증까지 통과해야 설치를 완료합니다.

## 진단과 수정 과정

1. 오류 로그에서 게임이 그래픽 화면을 만들기 전 약 3초 만에 `E01300B0`으로 종료되는 것을 확인했습니다.
2. Wine 추적에서 게임이 Nexon `gamescale64.dll`의 서명은 유효하다고 판단하지만, 인증서 체인이 잘못된 자체 서명 G4 루트에서 끝나는 것을 확인했습니다. 직후 게임 내부 예외가 발생했습니다.
3. 설치된 게임 파일의 서명에서 교차 서명 G4 인증서를 추출하고, DigiCert Assured ID Root CA까지 서명이 연결되는지 검증했습니다.
4. CrossOver 엔진을 해당 보틀 안에만 복제해 인증서 선택을 조정했습니다. 검증 결과는 4단계 체인, `WinVerifyTrust=0`, 게임이 요구하는 루트 지문 일치였습니다.

## 이 패치가 하는 일

2026년 한국 서비스 전환 뒤 게임은 Nexon `gamescale64.dll`의 서명 인증서를 검사합니다. 이 검사는 신뢰 체인의 최상위 인증서 SHA-1이 아래 값과 일치해야 통과합니다.

```
0563B8630D62D75ABBC8AB1E4BDFB5A899B24D43
```

macOS에서 CrossOver가 인증서를 가져오는 순서 때문에, 같은 DigiCert G4 계열의 자체 서명 루트 인증서가 먼저 선택될 수 있습니다.

| 역할 | 인증서 SHA-1 |
| --- | --- |
| 게임이 요구하는 DigiCert Assured ID Root CA | `0563B8630D62D75ABBC8AB1E4BDFB5A899B24D43` |
| 필요한 DigiCert Trusted Root G4 교차 서명 인증서 | `A99D5B79E9F1CDA59CDAB6373169D5353F5874C6` |
| 잘못 선택될 수 있는 DigiCert G4 자체 서명 루트 | `DDFB16CD4931C973A2037D3FC83A4D7D775D05E4` |

패키지에 들어 있는 공개 교차 서명 인증서는 게임 파일의 서명에서 추출해 지문과 서명 관계를 확인한 것입니다. 설치 프로그램은 이를 보틀의 Windows 인증서 저장소에 넣고, 그 보틀에서만 잘못된 G4 루트를 후보에서 제외합니다. 기존 루트는 원상복구할 때 다시 넣습니다. Windows 서명 검사가 올바른 4단계 체인을 만들도록 하며, 서명 검증이나 안티치트를 끄지 않습니다. 게임 파일과 Nexon 안티치트 파일도 바꾸지 않습니다.

## 설치 전 확인

- macOS, CrossOver, Python 3, 시스템 기본 `clang`과 코드 서명이 필요합니다.
- CrossOver가 설치되어 있어야 합니다.
- 오버워치 보틀 안에 `_retail_/Overwatch.exe`가 있어야 합니다.
- 설치 중에는 대상 오버워치 보틀의 Wine 프로세스만 종료될 수 있습니다. 게임과 Battle.net을 닫은 뒤 실행하세요.

폴더 구성: `install.sh`는 설치, `uninstall.sh`는 원상복구, `installer.py`는 실제 설치 코드입니다. `native/`와 `probe/`에는 소스와 진단 도구가 있고 `certs/`에는 지문을 고정해 검증하는 공개 인증서가 들어 있습니다. `.gitignore`는 빌드 산출물과 임시 로그를 제외합니다. `.sh`는 macOS의 zsh에서 실행됩니다. Finder에서 더블클릭하면 실행 대신 편집기로 열릴 수 있으므로 Terminal에서 실행하세요.

설치 프로그램은 CrossOver 앱과 오버워치 보틀을 자동으로 찾습니다. 여러 CrossOver 앱 또는 오버워치 보틀을 쓰는 경우에는 아래의 고급 실행 방법으로 경로를 지정할 수 있습니다.

## 설치 방법

1. Terminal을 엽니다.
2. 아래 명령을 실행합니다.
3. 완료되면 CrossOver 홈에서 Battle.net 또는 오버워치 항목을 실행합니다.

```zsh
cd ~/Downloads/crossover-nexon-overwatch-fix
./install.sh
```

출처를 확인할 수 없는 파일이라면 실행하지 마세요.

## 실행 전 점검과 고급 실행

아무것도 바꾸지 않고 탐지 결과만 보려면:

```zsh
python3 installer.py --check
```

`--check`는 설치 경로와 보틀 설정만 확인합니다. 실제 인증서 체인은 `./install.sh`가 검사하며, 이전에 설치한 보틀에서 중복 루트 인증서가 다시 등록됐다면 해당 인증서만 제거하고 다시 검증합니다.

CrossOver 앱과 보틀의 실제 경로를 지정하려면:

```zsh
python3 installer.py --app "/Applications/CrossOver.app" --bottle-dir "/Users/사용자이름/Library/Application Support/CrossOver/Bottles/Overwatch"
```

`사용자이름` 부분은 본인의 macOS 계정 이름으로 바꾸고, `Overwatch` 부분은 실제 보틀 폴더 이름으로 바꾸세요.

## CrossOver 홈에서 실행하는 방법

기본 Battle.net 메뉴 항목의 `Type=Windows` 실행 방식은 CrossOver의 다른 로더를 사용할 수 있습니다. 그 경로에서는 Wine이 macOS 인증서를 다시 가져오면서 이 패치가 제외한 G4 루트가 다시 등록될 수 있습니다.

설치 프로그램은 대상 보틀의 Battle.net 및 오버워치 메뉴 항목을 `Raw` 형식으로 바꾸고, CrossOver가 보틀 안에 생성한 셸 실행기를 연결합니다. 따라서 CrossOver 홈에서 해당 항목을 실행해도 보틀의 사설 Wine 런타임으로 시작합니다.

CrossOver가 메뉴를 동기화하거나 업데이트하면 이 메뉴 항목이 다시 만들어져 변경 내용이 사라질 수 있습니다. 그 뒤 실행 오류가 다시 나타나면 Battle.net과 오버워치를 종료한 뒤 이 폴더에서 `./install.sh`를 다시 실행하세요. 제거 프로그램은 이 패치가 변경한 메뉴 항목의 필드만 설치 전 값으로 복원합니다.

## 설치 후 확인

정상이라면 실행 직후 종료되지 않고, 새 오류 로그에 같은 `E01300B0`가 반복되지 않아야 합니다.

문제가 계속되면 다음 파일의 가장 최근 오류 로그를 함께 확인하세요.

```
~/Documents/Overwatch/Logs/errors/
```

로그에는 계정, 컴퓨터 정보, 경로가 들어갈 수 있습니다. 공개 장소에 올리기 전에는 이런 내용을 가리세요. 인증서 오류가 아닌 새 오류가 나온 경우에는 이 패치의 범위 밖일 수 있으므로, 가장 최근 파일명과 처음 나오는 오류 코드만 전달하면 다음 원인을 분리할 수 있습니다.

## 되돌리기

Terminal에서 이 폴더로 이동해 실행하세요.

```zsh
cd ~/Downloads/crossover-nexon-overwatch-fix
./uninstall.sh
```

설치 프로그램은 보틀 안 `overwatch-cert-fix/backups`에 설치 전 설정 백업을 만듭니다. 제거 프로그램은 이 패치가 추가한 환경 변수, Wine 경로 설정, 인증서 항목과 패치가 소유한 메뉴 항목 필드를 되돌리고, 설치 전 있던 루트 인증서도 복원합니다. 다른 보틀 설정이나 게임 파일은 건드리지 않습니다. 패치 파일과 백업은 이름을 바꿔 비활성 상태로 보관하므로 다시 설치할 수 있습니다.

## 유지 관리

이 패치는 CrossOver의 설치 파일을 변경하지 않고, 오버워치 보틀 안에 별도 Wine 런타임 복사본을 둡니다. APFS 복제본은 처음에는 약 1GB의 논리 용량으로 보일 수 있지만, 실제 추가 저장 공간은 변경된 부분만 사용합니다.

CrossOver 업데이트 뒤에도 이 보틀은 패치를 설치할 때 복제한 Wine 런타임을 사용합니다. 새 CrossOver 런타임으로 다시 적용하려면 먼저 `uninstall.sh`로 원상복구한 뒤 `install.sh`를 실행하세요. 설치 프로그램이 필요한 파일과 인증서 체인을 다시 검증합니다.

## 참고 문서

- [넥슨 오버워치 계정 및 서비스 FAQ](https://overwatch.nexon.com/support/faq/account)
- [Wine 11 호스트 인증서 가져오기 구현](https://github.com/wine-mirror/wine/blob/db11d0fe6a169c457e23d007e20404643d067aa8/dlls/crypt32/rootstore.c#L667-L800)
- [한국 오버워치 인증서 체인 분석](https://github.com/seolcu/overwatch-nexon-linux-fix/blob/main/docs/ANALYSIS.md)
