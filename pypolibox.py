#!/usr/bin/env python
# -*- coding: utf-8 -*-

#TODO: fix Facts.generate_lastbook_facts: keyword values should not contain ' ', e.g. set([' ', 'pragmatics']) 

#TODO: fix database db_item plang empty fuckup:
#      introduce sanity checks in sqlite? proglang is a string but must contain either         
#      nothing or at least a set of brackets '[]'
#      better way to store string arrays in sqlite? 
    #>>> f = gen_facts(["-l", "English"])
    
    #Traceback (most recent call last):
      #File "<pyshell#6>", line 1, in <module>
        #f = gen_facts(["-l", "English"])
      #File "pypolibox.py", line 48, in gen_facts
        #return Facts(Books(Results(Query(arg))))
      #File "pypolibox.py", line 216, in __init__
        #book_item = Book(result, results.db_columns)
      #File "pypolibox.py", line 241, in __init__
        #proglang_array = db_item[db_columns["plang"]].encode(DEFAULT_ENCODING)
    #AttributeError: 'NoneType' object has no attribute 'encode'

#TODO: maybe replace older/newer short/long w/ directive + measure (+/-/=, pages/age), cf. WeatherReporter

#TODO: scrape keywords from google book feeds
#      checked: the gbooks keywords are not part of the API
#TODO: how to query lang = ANY in SQLite?

import sqlite3
import sys
import argparse
import re # for "utils"
import datetime
import locale

language, encoding = locale.getlocale()
DEFAULT_ENCODING = encoding # sqlite stores strings as unicode, but the user input is likely something else
DB_FILE = 'pypolibox.sqlite'
BOOK_TABLE_NAME = 'books' # name of the table in the database file that contains info about books
CURRENT_YEAR = datetime.datetime.today().year 

argv = [ ["-k", "pragmatics"], \
         ["-k", "pragmatics", "semantics"], \
         ["-l", "German"], \
         ["-l", "German", "-p", "Lisp"], \
         ["-l", "German", "-p", "Lisp", "-k", "parsing"], \
         ["-l", "English", "-s", "0", "-c", "1"], \
         ["-l", "English", "-s", "0", "-e", "1", "-k", "discourse"], \
        ] # list of possible query arguments for debugging purposes

def debug_facts(argv): 
    """debugging function to check if all facts are created correctly"""
    facts = []
    for arg in argv:
        tmp = Facts(Books(Results(Query(arg))))
        facts.append(tmp)
    
    for f in facts:
        print "\n\n========================================================="
        print f.query_args
        for book in f.books:
            print book['query_facts']
            #if book.has_key("lastbook_facts"): # the 1st item doesn't have a preceding one...
             #   print book["lastbook_facts"]
    return facts

def gen_facts(arg):
    return Facts(Books(Results(Query(arg))))

def gen_props(arg):
    return Propositions(Facts(Books(Results(Query(arg)))))
    
#conn.commit() # commit changes to db
#conn.close() # close connection to db. 
#               DON't do this before all results are stored in a Book() instance

class Query:
    """ a Query() instance represents one user query to the database """

    def __init__ (self, argv):
        """ 
        parses commandline options with argparse, constructs a valid sql query and stores the resulting query in self.query
        """
        self.queries = []
        parser = argparse.ArgumentParser()
        
        parser.add_argument("-k", "--keywords", nargs='+', help="Which topic(s) should the book cover?") #nargs='+' handles 1 or more args    
        parser.add_argument("-l", "--language",
            help="Which language should the book have?")
        parser.add_argument("-p", "--proglang", nargs='+',
            help="Which programming language(s) should the book use?")
        parser.add_argument("-s", "--pagerange", type=int,
            help="book length ranges. 0 = less than 300 pages, " \
                "1 = between 300 and 600 pages. 2 = more than 600 pages.")
        parser.add_argument("-t", "--target", type=int,
            help="target audience. 0 = beginner, 1 = intermediate" \
                 "2 = advanced, 3 = professional")
        parser.add_argument("-e", "--exercises", type=int,
            help="Should the book contain exercises? 0 = no, 1 = yes")
        parser.add_argument("-c", "--codeexamples", type=int,
            help="Should the book contain code examples? 0 = no, 1 = yes")
        parser.add_argument("-r", "--minresults", type=int,
            help="show no less than MINRESULTS books") #TODO: currently unused
            # minresults should trigger a fallback query to the db to get more results
            # e.g. combine the user's parameters with OR instead of AND:
            #       use some form of weigths to get the "best" results, e.g.
            #       keywords * 3 + language * 2 + other_parameters * 1
        
        #TODO: put the if.args stuff into its own method (maybe useful, if
        # there's a WebQuery(Query) class
        args = parser.parse_args(argv)
            
        if args.keywords:
            for keyword in args.keywords:
                self.queries.append(self.substring_query("keywords", keyword))
        if args.language:
            self.queries.append(self.string_query("lang", args.language))
        if args.proglang:
            for proglang in args.proglang:
                self.queries.append(self.substring_query("plang", proglang))
        if args.pagerange:
            self.queries.append(self.pages_query(args.pagerange))
        if args.target:
            # 0 beginner, 1 intermediate, 2 advanced, 3 professional
            #db fuckup: advanced is encoded as "3"
            assert args.target in (0, 1, 2, 3)
            self.queries.append(self.equals_query("target", args.target))
        if args.exercises:
            assert args.exercises in (0, 1)
            self.queries.append(self.equals_query("exercises", args.exercises))
        if args.codeexamples:
            assert args.codeexamples in (0, 1)
            self.queries.append(self.equals_query("examples", args.codeexamples))
    
        #print "The database will be queried for: {0}".format(self.queries)
        self.query_args = args # we may need these for debugging
        self.query = self.construct_query(self.queries)
        #print "\nThis query will be sent to the database: {0}\n\n".format(self.query)

    def construct_query(self, queries):
        """takes a list of queries and combines them into one complex SQL query"""
        #query_template = "SELECT titel, year FROM books WHERE "
        query_template = "SELECT * FROM books "
        where = "WHERE "
        combined_queries = ""
        if len(queries) > 1:
            for query in queries[:-1]: # combine queries with " AND ", but don't append after the last query
                combined_queries += query + " AND "
            combined_queries += queries[-1]
            return query_template + where + combined_queries
        elif len(queries) == 1: # simple query, no combination needed
            query = queries[0] # list with one string element --> string
            #print "type(queries): {0}, len(queries): {1}".format(type(queries), len(queries))
            return query_template + where + query
        else: #empty query
            return query_template # query will show all books in the db

    def pages_query(self, length_category):
        assert length_category in (0, 1, 2) # short, medium length, long books
        if length_category == 0:
            return "pages < 300"
        if length_category == 1:
            return "pages >= 300 AND pages < 600"
        if length_category == 2:
            return "pages >= 600"
    
    def substring_query(self, sql_column, substring):
        sql_substring = "'%{0}%'".format(substring) # keyword --> '%keyword%' for SQL LIKE queries
        substring_query = "{0} like {1}".format(sql_column, sql_substring)
        return substring_query
    
    def string_query(self, sql_column, string):
        """find all database items that completely match a string
           in a given column, e.g. WHERE lang = 'German' """
        return "{0} = '{1}'".format(sql_column, string)
    
    def equals_query(self, sql_column, string):
        return "{0} = {1}".format(sql_column, string)

    def __str__(self):
        return "The arguments (parsed from the command line):\n{0}\nhave resulted in the following SQL query:\n{1}".format(q.query_args, q.query)


class Results:
    """ a Results() instance represents the results of a database query """
    
    def __init__ (self, q):
        """
        initialises a connection to the db, sends an sql query to the db 
        and and stores the results in self.query_results
        
        @type q: instance of class C{Query}
        @param q: an instance of the class Query()
        """
        self.query_args = q.query_args # keep original queries for debugging
        self.query = q.query
        
        conn = sqlite3.connect(DB_FILE)
        self.curs = conn.cursor() #TODO: i needed to "self" this to make it available in get_table_header(). it might be wise to move connect/cursor to the "global variables" part of the code.

        self.db_columns = self.get_table_header(BOOK_TABLE_NAME) #NOTE: this has to be done BEFORE the actual query, otherwise we'll overwrite the cursor!
        
        temp_results = self.curs.execute(q.query)
        self.query_results = []
        for result in temp_results:
            self.query_results.append(result) # temp_result is a LIVE SQL cursor, so we need to make the results 'permanent', e.g. by writing them to a list
    
    def __str__(self):
        """a method that prints all items of a query result to stdout"""
        return_string = "The query:\n{0}\n\nreturned the following results:\n\n".format(self.query)
        for book in self.query_results:
            return_string += str(book) + "\n"
        return return_string

    def get_table_header(self, table_name):
        """
        get the column names (e.g. title, year, authors) and their index from the books table of the db and return them as a dictionary.
        """
        table_info = self.curs.execute('PRAGMA table_info({0})'.format(table_name))
        db_columns = {}
        for index, name, type, notnull, dflt_value, pk in table_info:
            db_columns[name.encode(DEFAULT_ENCODING)] = index
        return db_columns


class Books:
    """
    a Books() instance represents ALL books that were found by a database query 
    as a list of Book() instances saved to self.books 
    """

    def __init__ (self, results):
        """
        @type results: C{Results}
        @param results: an instance of the class Results() containing the results from a database query

        This method generates a list of Book() instances (saved as self.books), each representing one book from a database query.
        """
        
        self.query_args =  results.query_args # original query arguments for debugging
        self.books = []
        for result in results.query_results:
            book_item = Book(result, results.db_columns, results.query_args)
            self.books.append(book_item)
    
    def __str__(self):
        return_string = ""
        for index, book in enumerate(self.books):
            book_string = "index: {0}\n{1}\n".format(index, book.__str__())
            return_string += book_string
        return return_string

class Book:
    """ a Book() instance represents ONE book from a database query """
    def __init__ (self, db_item, db_columns, query_args):
        """
        fill Book() instance w/ metadata from the db

        @type db_item: C{tuple}
        @param db_item: an item from the C{sqlite3.Cursor} object that contains
        the results from the db query.
        
        @type db_columns: C{dict}
        @param db_columns: a dictionary of table columns (e.g. title, authors) from the database
        
        @type query_args: C{argparse.Namespace}
        @param query_args: a key/value store containing the original user query
        """
        self.query_args = query_args #needed for generating query facts later on
        
        self.title = db_item[db_columns["title"]].encode(DEFAULT_ENCODING)
        self.year = db_item[db_columns["year"]]

        authors_array = db_item[db_columns["authors"]].encode(DEFAULT_ENCODING)
        self.authors = sql_array_to_set(authors_array)

        keywords_array = db_item[db_columns["keywords"]].encode(DEFAULT_ENCODING)
        self.keywords = sql_array_to_set(keywords_array)

        self.language = db_item[db_columns["lang"]].encode(DEFAULT_ENCODING)
        
        proglang_array = db_item[db_columns["plang"]].encode(DEFAULT_ENCODING)
        self.proglang = sql_array_to_set(proglang_array)
        
        #TODO: proglang should be an "sql_array" (1 book w/ 2 programming languages),
        #      but there's only one book in the db that is handled that way
        #      all other plang columns in the db are "ordinary" strings (e.g. no '[' or ']')

        self.pages = db_item[db_columns["pages"]]
        if self.pages < 300:
            self.pagerange = 0
        elif self.pages >= 300 and self.pages < 600:
            self.pagerange = 1
        elif self.pages >= 600:
            self.pagerange = 2
            
        self.target = db_item[db_columns["target"]]
        self.exercises = db_item[db_columns["exercises"]]
        self.codeexamples = db_item[db_columns["examples"]]
        
    def __str__(self):
        return_string = ""
        for key, value in self.__dict__.iteritems():
            return_string += "{0}:\t\t{1}\n".format(key, value)
        return return_string


class AllFacts():
    """
    AllFacts() represents facts about a Books() instance, which is a list of Book() instances
    """
    def __init__ (self, b):
        """ 
        @type b: C{Books}
        @param b: an instance of the class Books        
        """
        self.query_args = b.query_args # originall query args for generating query_facts
        self.books = []
        for index, book in enumerate(b.books):
            if index == 0: #first book
                book_facts = Facts(book, index)
                self.books.append(book_facts)
            else: # every other book --> trigger comparison with preceeding book
                preceding_book = b.books[index-1]
                book_facts = Facts(book, index, preceding_book)
                self.books.append(book_facts)
                
    def __str__(self):
        return_string = ""
        for index, book in enumerate(self.books):
            return_string += "facts about book #{0}:\n".format(index) + \
                             "--------------------\n" + \
                             "{0}\n\n".format(book)
        return return_string

class Facts():
    """ Facts() represents facts about a single Book() instance """
    def __init__ (self, book, index=0, preceding_book=False):
        """
        facts are ultimately retrieved from sqlite3, where all strings are encoded as <type 'unicode'>, not as <type 'str'>! in order to compare user queries of <type 'str'> to <type 'unicode'> strings from the database, we'll need to convert them.
        
        convert <type 'str'> to <type 'unicode'>: some_string.decode(DEFAULT_ENCODING)
        """
        facts = {}
                
        facts["id_facts"] = self.generate_id_facts(index, book)
        facts["extra_facts"] = self.generate_extra_facts(index, book)
        facts["query_facts"] = self.generate_query_facts(index, book)
                
        if preceding_book == False: # if this is the first/only book            
            pass # DON't compare this book to a non-existent preceeding one
        else:
            facts["lastbook_facts"] = self.generate_lastbook_facts(index, book, preceding_book) # generate additional facts, comparing the current with the preceeding book        
        self.facts = facts

    def generate_id_facts(self, index, book):
        """ 
        returns a dictionary of id facts about the current book
        
        instead of writing lots of repetitive code like in JPolibox:
        
            id_facts["authors"] = book.authors
            id_facts["codeexamples"] = book.codeexamples ...
            
        get all those book attributes at once (getattr) and turn them into dictionary items (__setitem__).
        """
        id_facts = {}
        attributes = ['authors', 'codeexamples', 'exercises', 'keywords', 'language', 'pages', 'proglang', 'target', 'title', 'year']
        
        for attribute in attributes:
            book_attribute = getattr(book, attribute)
            id_facts.__setitem__(attribute, book_attribute)
                
        return id_facts
        
    def generate_query_facts(self, index, book):
        """ generate facts that describes if a book matches (parts of) the query"""
        query_facts = {}
        query_facts["usermodel_match"] = {}
        query_facts["usermodel_nomatch"] = {}
        query_args = book.query_args
        simple_attributes = ['codeexamples', 'exercises', 'language', 'pagerange', 'target']
        complex_attributes = ['keywords', 'proglang'] # may contain more than 1 value
        
        for simple_attribute in simple_attributes:
            if getattr(query_args, simple_attribute): #if query_args has a non-empty value for this attrib
                if getattr(query_args, simple_attribute) == getattr(book, simple_attribute):
                    query_facts["usermodel_match"][simple_attribute] = getattr(book, simple_attribute)
                else:
                    query_facts["usermodel_nomatch"][simple_attribute] = getattr(book, simple_attribute) 
                    
        for complex_attribute in complex_attributes:
            if getattr(query_args, complex_attribute): # if query_args has at least one value for this attrib
                values = getattr(query_args, complex_attribute)
                matching_values = set()
                nonmatching_values = set()
                for value in values:
                    if value in getattr(book, complex_attribute):
                        matching_values.add(value)
                    else:
                        nonmatching_values.add(value)
                if matching_values != set(): # if not empty ...
                    query_facts["usermodel_match"][complex_attribute] = matching_values
                if nonmatching_values != set():
                    query_facts["usermodel_nomatch"][complex_attribute] = nonmatching_values

        return query_facts
                
    def generate_lastbook_facts(self, index, book, preceding_book):
        
        lastbook_facts = {}
        lastbook_facts['lastbook_match'] = {}
        lastbook_facts['lastbook_nomatch'] = {}
        simple_comparisons = ['codeexamples', 'exercises','language', 'target']
        set_comparisons = ['keywords', 'proglang']
        
        for simple_comparison in simple_comparisons:
            if getattr(book, simple_comparison) == getattr(preceding_book, simple_comparison):
                lastbook_facts['lastbook_match'][simple_comparison] = getattr(book, simple_comparison)
            else:
                lastbook_facts['lastbook_nomatch'][simple_comparison] = getattr(book, simple_comparison)
                
        for attribute in set_comparisons:
            current_attrib = getattr(book, attribute)
            preceding_attrib = getattr(preceding_book, attribute)
            if current_attrib == preceding_attrib == set([]):
                pass # nothing to compare
            else:
                shared_values = current_attrib.intersection(preceding_attrib)
                if shared_values != set([]):
                    lastbook_facts['lastbook_match'][attribute] = shared_values
                
                non_shared_values = current_attrib.symmetric_difference(preceding_attrib)
                lastbook_facts['lastbook_nomatch'][attribute] = non_shared_values
                
                current_only_values = current_attrib.difference(preceding_attrib)
                if current_only_values != set([]):
                    fact_name = attribute + '_current_book_only'
                    lastbook_facts['lastbook_nomatch'][fact_name] = current_only_values

                preceding_only_values = preceding_attrib.difference(current_attrib)
                if preceding_only_values != set([]):
                    fact_name = attribute + '_preceding_book_only'
                    lastbook_facts["lastbook_nomatch"][fact_name] = preceding_only_values
 
        if book.year == preceding_book.year:
            lastbook_facts["lastbook_match"]["year"] = book.year
        else:
            if book.year > preceding_book.year:
               years_diff = book.year - preceding_book.year 
               lastbook_facts["lastbook_nomatch"]["newer"] = years_diff
            else:
                years_diff = preceding_book.year - book.year
                lastbook_facts["lastbook_nomatch"]["older"] = years_diff

        if book.pagerange == preceding_book.pagerange:
            lastbook_facts["lastbook_match"]["pagerange"] = book.pagerange
        else:
            if book.pages > preceding_book.pages:
                page_diff = book.pages - preceding_book.pages
                lastbook_facts["lastbook_nomatch"]["longer"] = page_diff
            else: #current book is shorter
                page_diff = preceding_book.pages - book.pages
                lastbook_facts["lastbook_nomatch"]["shorter"] = page_diff
                
        return lastbook_facts
    
    def generate_extra_facts(self, index, book):
        """ compare current book w/ predefined values and generate facts"""
        extra_facts = {}
        if book.pages < 100:
            extra_facts["pages"] = "very short"
        if book.pages > 600:
            extra_facts["pages"] = "very long"
        if (CURRENT_YEAR - 10) < book.year: # newer than 10 years
            extra_facts["year"] = "recent"
        if (CURRENT_YEAR - 30) > book.year: # older than 30 years
            extra_facts["year"] = "old"
        
        return extra_facts

    def __str__(self):
        """returns a string representation of a Facts() instance, but omits empty values"""
        signifiers_of_emptyness = [ [], {}, set() ] # lists, dicts, sets can be empty
        return_string = ""
        for key, value in self.facts.iteritems():
            if value not in signifiers_of_emptyness:
                return_string += "\n{0}:\n".format(key)
                for attribute, val in value.iteritems():
                    if val not in signifiers_of_emptyness:
                        return_string += "\t{0}: {1}\n".format(attribute, val)
        return return_string        


class AllPropositions:
    """
    contains propositions about ALL the books that were listed in a query result
    """
    def __init__ (self, allfacts):
        """
        @type facts: I{AllFacts}
        """
        self.allpropostions = []
        for book in allfacts.books:
            book_propositions = Propositions(book)
            self.allpropostions.append(book_propositions)

    def __str__(self):
        return_string = ""
        for index, propositions in enumerate(self.allpropostions):
            return_string += "propositions about book #{0}:\n".format(index) + \
                             "----------------------------\n" + \
                             "{0}\n\n".format(propositions)
        return return_string
        
class Propositions():
    """ 
    represents propositions (positive/negative/neutral ratings) of a single book. Propositions() are generated from Facts() about a Book().
    """ 
    def __init__ (self, facts):
        """
        @type facts: I{Facts}
        """
        facts = facts.facts # a Facts() stores its facts in .facts; this line saves some typing
        propositions = {}
        propositions['usermodel_match'] = {}
        propositions['usermodel_nomatch'] = {}
        propositions['lastbook_match'] = {}
        propositions['lastbook_nomatch'] = {}
        propositions['extra'] = {}
        propositions['id'] = {}
        
        for attribute, value in facts['query_facts']['usermodel_match'].iteritems():
            propositions['usermodel_match'][attribute] =  (value, 'positive')
        for attribute, value in facts['query_facts']['usermodel_nomatch'].iteritems():
            propositions['usermodel_nomatch'][attribute] = (value, 'negative')
            
        if facts.has_key('lastbook_facts'): # 1st book doesn't have this
            for attribute, value in facts['lastbook_facts']['lastbook_match'].iteritems():
                propositions['lastbook_match'][attribute] =  (value, 'neutral') # neutral (not positive, since it's not related 2 usermodel)
            for attribute, value in facts['lastbook_facts']['lastbook_nomatch'].iteritems():
                propositions['lastbook_nomatch'][attribute] = (value, 'neutral')
        
        if facts['extra_facts'].has_key('year'):
            if facts['extra_facts']['year'] == 'recent':
                propositions['extra']['year'] = (facts['extra_facts']['year'], 'positive')
            elif facts['extra_facts']['year'] == 'old':
                propositions['extra']['year'] = (facts['extra_facts']['year'], 'negative')
                
        if facts['extra_facts'].has_key('pages'):
            propositions['extra']['pages'] = (facts['extra_facts']['pages'], 'neutral')

        for fact in facts['id_facts']:
            other_propositions = self.__do_not_use_twice(propositions)
            if fact not in other_propositions:
                propositions['id'][fact] = (facts['id_facts'][fact], 'neutral')
            #else: #TODO: remove lines after debugging
                #for proposition_type in propositions.keys():
                    #if propositions[proposition_type].has_key(fact):
                        #print "will not generate id fact about '{0}', as this one is already present in {1}, namely: {2}".format(fact, proposition_type, propositions[proposition_type][fact])

        self.propositions = propositions
            
    def __do_not_use_twice(self, propositions):
        """generates the set of proposition attributes that have been used before
        
        (e.g. as usermodel propositions, lastbook propositions, extra propositions) and should therefore not be used again to generate id propositions
        
        Example: If there is an Extra/UserModelMatch etc. Proposition about "Pages" (e.g. >= 600) or Year, there should be no ID Proposition about the same fact.
        """
        attributes = set()
        for proposition_type in propositions.keys():
            attrib_list = propositions[proposition_type].keys()
            #print "proposition type {0} has these attributes: {1}".format(proposition_type, attrib_list)
            for attribute in attrib_list:
                attributes.add(attribute)
        return attributes

    def __str__(self):
        return_string = ""
        for key, value in self.propositions.iteritems():
            return_string += "\n{0}:\n".format(key)
            for attribute in value.iteritems():
                return_string += "\t{0}\n".format(attribute)
        return return_string 

class Messages:
    """
    represents all Messages generated from Propositions() about a Book()
    """
    
    def __init__ (self, propositions_list):
        """ Class initialiser """
        self.messages = []


    def generate_id_messages(self, propositions):
        pass
        

#TODO: move helper functions to utils.py; complete unfinished ones

def sql_array_to_set(sql_array):
    """
    books.db uses '[' and ']' tohandle attributes w/ more than one value:
    e.g. authors = '[Noam Chomsky][Alan Touring]'

    this function turns those multi-value strings into a set with separate values
    """
    item = re.compile("\[(.*?)\]")
    items = item.findall(sql_array)
    item_set = set()
    for i in items:
        item_set.add(i)
    return item_set

def test_sql():
    """a simple sql query example to play around with"""
    query_results = curs.execute('''select * from books where pages < 300;''')
    print "select * from books where pages < 300;\n\n"
    return query_results

def test_cli():
    """run several complex queries and print their results to stdout"""
    argvectors = [ ["-k", "pragmatics"], \
                   ["-k", "pragmatics", "semantics"], \
                   ["-l", "German"], \
                   ["-l", "German", "-p", "Lisp"], \
                   ["-l", "German", "-p", "Lisp", "-k", "parsing"], \
                   ["-l", "English", "-s", "0", "-c", "1"], \
                   ["-l", "English", "-s", "0", "-e", "1", "-k", "discourse"], \
                ]
    for argv in argvectors:
        book_list = Books(Results(Query(argv)))
        print "{0}:\n\n".format(argv)
        for book in book_list.books:
            print book.title, book.year


if __name__ == "__main__":
    #commandline_query = parse_commandline(sys.argv[1:])
    q = Query(sys.argv[1:])
    #q.parse_commandline(sys.argv[1:])
    results = Results(q)
    print results
    p = gen_props(argv[2])
    
