import logging
import condmcp.autocond as ac
from multiprocessing import Pool


def task(ind):
    conditionner = ac.Conditionner('MPOD:', str(ind), 'seq.csv')


def main():
    with Pool(4) as p:
        p.map(task, [0])
    return 0


if __name__ == "__main__":
    # execute only if run as a script
    main()
