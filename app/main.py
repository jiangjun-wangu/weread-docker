"""CLI 入口：login / shelf / download / sync"""
import argparse
import sys
import time

from app import auth
from app import client
from app import store
from app.downloader import Downloader


def print_qr(url):
    import qrcode
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    qr.print_ascii(invert=True)


def cmd_login(args):
    a = auth.WeReadAuth()
    uid = a.fetch_uid()
    url = a.qr_url()
    print("二维码 URL: " + url)
    print("")
    print_qr(url)
    print("")
    print("请用微信扫码，等待确认...")
    ok = a.wait_for_login(timeout=args.timeout)
    if not ok:
        print("登录超时或失败")
        a.close()
        return 1
    a.save()
    print("登录成功，session 已保存")
    a.close()
    return 0


def _build_client():
    a = auth.WeReadAuth()
    if not a.load():
        print("未登录，请先运行 login")
        return None, None
    return a, client.WeReadClient(a)


def cmd_shelf(args):
    a, cli = _build_client()
    if not cli:
        return 1
    try:
        books = cli.shelf()
    except client.SessionExpired:
        print("Session 过期，请重新登录")
        a.close()
        return 1
    print("书架共 " + str(len(books)) + " 本:")
    for i, b in enumerate(books, 1):
        print(str(i) + '. ' + b['title'] + ' - ' + b['author'] + ' [' + b['bookId'] + ']')
    a.close()
    return 0


def cmd_download(args):
    a, cli = _build_client()
    if not cli:
        return 1
    try:
        books = cli.shelf()
        target = None
        for b in books:
            if b['bookId'] == args.book_id:
                target = b
                break
        if not target:
            print("书架中未找到 bookId: " + args.book_id)
            a.close()
            return 1
        d = Downloader(cli, interval=args.interval)
        d.download_book(target)
    except client.SessionExpired:
        print("Session 过期，请重新登录")
        a.close()
        return 1
    a.close()
    return 0


def cmd_sync(args):
    a, cli = _build_client()
    if not cli:
        return 1
    try:
        books = cli.shelf()
    except client.SessionExpired:
        print("Session 过期，请重新登录")
        a.close()
        return 1
    print("书架共 " + str(len(books)) + " 本，开始同步")
    d = Downloader(cli, interval=args.interval)

    def on_progress(i, total, title):
        print("[" + str(i) + "/" + str(total) + "] " + title)

    try:
        result = d.download_all(books, progress=on_progress)
    except client.SessionExpired:
        print("Session 过期，已下载部分保留")
        a.close()
        return 1
    print("")
    print("汇总: 成功=" + str(result["ok"]) + " 跳过=" + str(result["skipped"]) + " 失败=" + str(result["failed"]) + " 空=" + str(result["empty"]))
    a.close()
    return 0


def cmd_recount(args):
    from app import store
    before = store.load_rate()
    after = store.recount_rate_from_downloaded()
    month = __import__("time").strftime("%Y-%m")
    print("补计前:", before)
    print("补计后:", after)
    print("本月(" + month + ")已下:", after.get(month, 0), "本")
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="weread-downloader")
    sub = p.add_subparsers(dest="cmd")

    p_login = sub.add_parser("login", help="扫码登录")
    p_login.add_argument("--timeout", type=int, default=180)
    p_login.set_defaults(func=cmd_login)

    p_shelf = sub.add_parser("shelf", help="列出书架")
    p_shelf.set_defaults(func=cmd_shelf)

    p_dl = sub.add_parser("download", help="下载指定书籍")
    p_dl.add_argument("book_id")
    p_dl.add_argument("--interval", type=float, default=3.0)
    p_dl.set_defaults(func=cmd_download)

    p_sync = sub.add_parser("sync", help="全量同步书架")
    p_sync.add_argument("--interval", type=float, default=3.0)
    p_sync.set_defaults(func=cmd_sync)

    p_recount = sub.add_parser("recount", help="按已下载记录重算本月计数")
    p_recount.set_defaults(func=cmd_recount)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.cmd:
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
