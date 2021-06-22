import logging
import condmcp.autocond as ac
from multiprocessing import Pool


def task(ind):
    conditionner = ac.Conditionner('COND:', 'MCP' + str(ind) + ':', 'seq.csv')


def main():
    with Pool(2) as p:
        p.map(task, [1])
    return 0


if __name__ == "__main__":
    # execute only if run as a script
    main()