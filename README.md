# MFA-PoC-Environment

## 参考リンク

- [Google Authenticator を使って Amazon WorkSpaces に多要素認証ログイン](https://aws.typepad.com/sajp/2014/10/google-authenticator.html)
- [RADIUSサーバーを構築して、WorkSpacesを多要素認証で運用する](http://blog.serverworks.co.jp/tech/2020/01/21/workspaces-use-radius-mfa/)
- [Azure MFAサーバーを使用したAmazon WorkSpacesの多要素認証](https://aws.amazon.com/jp/blogs/news/amazon-workspaces-multi-factor-authentication-using-azure-mfa/)

## 前提

- デプロイは管理者権限を持つIAMユーザーの権限で行うため、IAMユーザーを用意して下さい。
- あらかじめ、環境をデプロイするリージョンにキーペアを用意して下さい。このキーペアをEC2インスタンスに設定します。
- 以下のソフウェアがインストール済みであることを確認して下さい。
    ```shell
    aws --version
    python3 --version
    node --version
    npm --version
    git --version
    jq --version
    ```
- 上記環境を整えるのが面倒な場合はCloud9の利用がお奨めです。以下の手順を参考にCloud9をセットアップしてください。
  - [Cloud9環境のセットアップ](https://github.com/sotoiwa/Analytics-PoC-Environment/blob/master/cloud9.md)

## CDKでのベースインフラストラクチャのデプロイ

### CDKのインストール

CDKをグローバルにインストールします。

```shell
npm install -g aws-cdk
```

### CDKプロジェクトのクローン

CDKプロジェクトをローカルにクローンします。

```shell
git clone https://github.com/sotoiwa/MFA-PoC-Environment.git
cd MFA-PoC-Environment
```

### Pythonの準備

Pythonのvirtualenvを作成して有効化します。

```shell
python3 -m venv .env
source .env/bin/activate
```

必要なpipモジュールをインストールします。

```shell
pip install -r requirements.txt
```

### 環境に合わせたカスタマイズ

`cdk.sample.json`を`cdk.json`としてコピーし、パラメータをいい感じに設定して下さい。

```shell
cp cdk.sample.json cdk.json
```

### インフラのデプロイ

CDKが使用するバケットを作成します。

```shell
cdk bootstrap
```

スタックをデプロイします。

```shell
cdk deploy *Stack --require-approval never
```

## 踏み台Windowsのドメイン参加（オプション）

ADの管理に使用できますが、WorkSpacesコンソールからユーザーを追加することもできるのでオプションです。

ここでは手動で参加します。

- [Windows インスタンスを手動で参加させる](https://docs.aws.amazon.com/ja_jp/directoryservice/latest/admin-guide/join_windows_instance.html)

ADのIPアドレスを確認します。

```shell
aws ds describe-directories | \
  jq -r '.DirectoryDescriptions[] | select( .Name == "corp.example.com" ) | .DnsIpAddrs[]'
```

踏み台インスタンスにRDPし、PowerShellを起動します。
あるいは、セッションマネージャーでPowerShellを起動します。

AD管理に必要なツールをPowerShellでインストールします。

```
Import-Module ServerManager
Get-WindowsFeature
Install-WindowsFeature -Name GPMC,RSAT-AD-Tools,RSAT-DNS-Server
Get-WindowsFeature
```

DNSサーバーを変更します。

```powershell
Get-NetAdapter | Get-DnsClientServerAddress
Get-NetAdapter | Set-DnsClientServerAddress -ServerAddresses <1つ目のDNSアドレス>,<2つ目のDNSアドレス>
Get-NetAdapter | Get-DnsClientServerAddress
```

ADに参加します。ユーザーはAWS Managed ADの場合は`Admnin`、Self-managed ADの場合は`Administrator`です。

```powershell
$user = 'corp.example.com\Admin'
$password = ConvertTo-SecureString -AsPlainText '<パスワード>' -Force
$Credential = New-Object System.Management.Automation.PsCredential($user, $password)
Add-Computer -DomainName corp.example.com -Credential $Credential
```

変更を反映するためリブートします。

```powershell
Restart-Computer -Force
```


## RADIUSサーバーの設定

epelリポジトリを有効化します。

```shell
sudo amazon-linux-extras install -y epel
```

RADIUSサーバーに必要なパッケージをインストールします。

```shell
sudo yum -y install freeradius freeradius-utils google-authenticator
```

RADIUS経由の認証を許可するグループを作成します。

```shell
sudo groupadd radius-enabled
```

ホスト名を設定しておきます。ホスト名は、後ほどGoogle Authenticatorに登録した際に、登録名で使われます。

```shell
sudo hostnamectl set-hostname radius.example.com
```

`/etc/hosts`ファイルに追加します。

```shell
echo $(hostname -I) $(hostname) | sudo tee -a /etc/hosts
```

`radiusd`を`root`ユーザーで動作させる必要があるため、設定を次の通り変更します。

```shell
sudo sed -i -e 's/user = radiusd/user = root/' /etc/raddb/radiusd.conf
sudo sed -i -e 's/group = radiusd/group = root/' /etc/raddb/radiusd.conf
```

`/etc/raddb/users`を開き、`radius-enabled`のグループに所属しているユーザーがradius認証されるように設定します。

```shell
cat <<EOF | sudo tee -a /etc/raddb/users
DEFAULT    Group != "radius-enabled", Auth-Type := Reject
       Reply-Message = "Your account has been disabled."
DEFAULT        Auth-Type := PAM
EOF
```

radius認証の際、内部ではpamが使われますが、これを有効化します。

```shell
sudo sed -i -e '/pam/s/#//' /etc/raddb/sites-available/default
```

RADIUS認証の際に、Google Authenticatorが使われるように設定します。

```shell
sudo vi /etc/pam.d/radiusd
```

下記の通りに書き換えます。

```
#%PAM-1.0
#auth       include     password-auth
#account    required    pam_nologin.so
#account    include     password-auth
#password   include     password-auth
#session    include     password-auth
auth requisite pam_google_authenticator.so
account required pam_permit.so
session required pam_permit.so
```

RADIUSがプロトコルを受け付けるクライアントについての設定をします。secretは適当に設定します。

```
cat <<EOF | sudo tee -a /etc/raddb/clients.conf 
client vpc {
        ipaddr = 10.1.0.0/16
        secret = XXXXXXXXXXXXXX
}
EOF
```

pamモジュールを有効化するため、シンボリックリンクを追加します。

```shell
sudo ln -s /etc/raddb/mods-available/pam /etc/raddb/mods-enabled/pam
```

`radiusd`の自動起動を有効化し、RADIUSサーバーを起動します。

```shell
sudo systemctl enable radiusd
sudo systemctl start radiusd
```

## RADIUSサーバーが認証するユーザーの設定

RADIUSサーバーはActive Directoryと連携している訳ではないので、RADIUSサーバー上にもActive Directoryと同じユーザーの追加が必要です。

Active Directory上のユーザー名を指定し、Linux上にユーザーを追加します。

```shell
sudo useradd -g radius-enabled sotosugi
```

ユーザーを追加したら、追加したユーザーの権限で、google-authenticatorを起動しましょう。

```shell
sudo -u sotosugi /usr/bin/google-authenticator
```

質問は全て`y`で進めます。
 
2次元コードを表示するURLと2次元コードが表示されます。

```output
[ec2-user@ip-10-1-2-126 ~]$ sudo -u sotosugi /usr/bin/google-authenticator

Do you want authentication tokens to be time-based (y/n) y
Warning: pasting the following URL into your browser exposes the OTP secret to Google:
  https://www.google.com/chart?chs=200x200&chld=M|0&cht=qr&chl=otpauth://totp/sotosugi@radius.example.com%3Fsecret%3DXXXXXXXXXXXXXXXXXXXXXXXXXX%26issuer%3Dradius.example.com

（省略）

Your new secret key is: XXXXXXXXXXXXXXXXXXXXXXXXXX
Your verification code is 598282
Your emergency scratch codes are:
  12194169
  76836024
  90480611
  63879847
  43631636

Do you want me to update your "/home/sotosugi/.google_authenticator" file? (y/n) y

Do you want to disallow multiple uses of the same authentication
token? This restricts you to one login about every 30s, but it increases
your chances to notice or even prevent man-in-the-middle attacks (y/n) y

By default, a new token is generated every 30 seconds by the mobile app.
In order to compensate for possible time-skew between the client and the server,
we allow an extra token before and after the current time. This allows for a
time skew of up to 30 seconds between authentication server and client. If you
experience problems with poor time synchronization, you can increase the window
from its default size of 3 permitted codes (one previous code, the current
code, the next code) to 17 permitted codes (the 8 previous codes, the current
code, and the 8 next codes). This will permit for a time skew of up to 4 minutes
between client and server.
Do you want to do so? (y/n) y

If the computer that you are logging into isn't hardened against brute-force
login attempts, you can enable rate-limiting for the authentication module.
By default, this limits attackers to no more than 3 login attempts every 30s.
Do you want to enable rate-limiting? (y/n) y
[ec2-user@ip-10-1-2-126 ~]$
```

## セキュリティグループ

Managed ADのENIを探し、セキュリティグループを確認し、Radiusサーバーのセキュリティグループへのアクセス（1812/UDP）を許可します。
Radiusサーバー側のインバウンドと、Managed ADの側のアウトバウンドを両方設定する必要があります。

## WorkSpaces

WorkSpacesを作成します。

### ディレクトリの登録

WorkSpacesコンソールで、「ディレクトリ」からManaged ADを「登録」します。

### WorkSpacesの作成

「WorkSpaces」から「WorkSpaceの起動」を行います。この画面でユーザーを作成できます。

WorkSpaceが起動したら一度ログインして確認します。

### MFAの有効化

MFAの有効化はAD Connectorの場合はWorkSpacesコンソールですが、Managed ADの場合はDirectory Serviceコンソールで行います。

|項目|値|備考|
|---|---|---|
|表示ラベル|radius.example.com||
|RADIUS サーバーの DNS 名または IP アドレス|||
|ポート|1812||
|共有シークレットコード|XXXXXXXXXXXXXX||
|プロトコル|PAP||
|サーバータイムアウト（秒単位)|30||
|RADIUS リクエストの最大再試行数|4||

もう一度WorkSpacesにログイン確認します。
