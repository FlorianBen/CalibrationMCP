import condmcp.autocond as ac
from multiprocessing import Pool
import argparse
from itertools import repeat


def task(ind, file):
    conditionner = ac.Conditionner('MPOD:', str(ind), file)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('channels', metavar='N', type=int, nargs='+',
                        help='Channel use for the conditioning')
    parser.add_argument("-s", "--seq", help="Sequence file", required=True)
    args = parser.parse_args()

    channels = args.channels
    fileseq = args.seq

    with Pool(4) as p:
        p.starmap(task, zip(channels, repeat(fileseq)))
    return 0


if __name__ == "__main__":
    # execute only if run as a script
    main()
