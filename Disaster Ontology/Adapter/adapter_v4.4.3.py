# coding=utf-8
"""Adapt raw material from uruguay csv to a simple owl 2 module in RDF/XML.
  May use the same for other countries of the same region?

  Notes: 
  
  When saving spreadsheet in csv, use § character as the deliminator.
  
  The uy data seemingly incldes only dates and sparql supports only xsd:dataTime; hence we
  assert dateTimes but with zero hours, minutes, and seconds part. Few tests needed to
  fix various errors in data.
  
  This script should be generalized to handle many local raw data types, etc.
  
  Distribution of labour between adapter and ontology mapping should be analyzed.
  (Using Protege for complex reasoning might be slow etc.)
  
  ON 2016
"""

import rdflib
from rdflib import URIRef, Literal, plugin, Graph
from rdflib.namespace import DC, OWL, RDF, XSD, Namespace, NamespaceManager
import sys
from rdflib.store import Store
import glob

import time
import codecs
#import io
import re

from calendar import monthrange

# Start the show...
startTime = time.time()

def fixAsLocalNames(fields): 
  """Convert raw field names to suitable URI local names."""
  badChars = [' ', '&', '$', '(', ')', '.' ]
  replaceChars = [ [u'á', u'a'], [u'é', u'e'], [u'í', u'i'], [u'ó', u'o'], [u'ú', u'u'] ]
  result = [] 
  for f in fields:
    x = f
    for c in badChars: # Remove bad chars (Usual replace does not work for Unicode :-( )
      x = x.replace(c,"")
    for c in replaceChars:
      x = x.replace(c[0],c[1])
    result.append(str(x)) # Also, try if works in ascii... (if fails, add new bad chars above etc.)
  return result

def describeFieldsAsOwlProperties(g,fields, fn):
# TO DO: Modify to add actual fields from global ontology instead of local ontology
  """Add simple terminology (to keep Protege happy...)"""
  for field in fields:
    if field not in fn:  # Only add fields in local ontology that are not already defined in global ontology
	  if fielf not in ignoredFields:
        g.add( (URIRef(nsSource+field), RDF.type, OWL.DatatypeProperty ) )
	else:
	  g.add( (URIRef(nsGlobal+fn[field]), RDF.type, OWL.DatatypeProperty ) )
  g.add( (URIRef(DisasterRecordType), RDF.type, OWL.Class) ) 
  g.add( (URIRef(hasOrigin), RDF.type, OWL.ObjectProperty) )
  g.add( (URIRef(fromFile), RDF.type, OWL.DatatypeProperty) )

def fixDate(ind, d):
  f = d.split("/")
#  print d
  try:
    if int(f[2])==0:
	  f[2] = '1'
    result = "%04d-%02d-%02d" % (int(f[0]), int(f[1]), int(f[2]))
    if int(f[0])==0 or int(f[1])==0 or int(f[2])==0:
      print "Warning (1): In source line %d, bad date value (%s), converting to None." % (ind+1, d)
      return None  

    # Sanity check for dates (data seems to include impossible dates which would lead into
    # inconsistent ontology...)
    mr = monthrange(int(f[0]), int(f[1]))
    #print mr[0], mr[1]
    if int(f[2])> mr[1]:
      print "Warning (2): In source line %d, bad date value (%s), converting to None." % (ind+1, d)
      return None  

  except (ValueError, IndexError):
    print "Warning (3): In source line %d, bad date value (%s), converting to None." % (ind+1, d)
    return None  
#  print result
  return Literal(result+"T00:00:00",datatype=XSD.dateTime) 

def addToModel(g,fields,data,ind,filename): # TODO: add countryCode, countryName, fieldNames, propertyTypes, ignoredFields
  """Add as statements to the model g. Note that a better approach might be harmonizing
     predicate names (fields) a bit already at this point?
  """
  for i in range(len(fields)): # Only add data that has a column header (i.e. predicate name)...
    # Check if it is an ignored field. If so, then skip it
    if fields[i] in ignoredFields:
      continue
    # Check if data is empty. If so, then skip it
    # This check is repeated below when attempting to create the object as precaution. We can either skip it here or below.
    if len(data[i])==0:
      continue
    # CREATE SUBJECT, PREDICATE AND OBJECT
    # SUBJECT (Object Name/ID - required for named individuals)
    subject = URIRef(nsSource+"record"+str(startTime)+"_"+str(ind)) # Object Name (NS_Source+timestamp+linenum)
    # PREDICATE (object property) (generalized to use global property names)
    #predicate = URIRef(nsSource+fields[i])
    predicateName = fields[i] # property name
    namespace = nsSource	# property namespace
    predicateType = None	# Property type
    if fields[i] in fieldNames[countryCode]: # If property exists in main ontology use global property name and namespace
      predicateName = fieldNames[countryCode][fields[i]] # Use property name from main (global disOnt) ontology
      namespace = nsGlobal # Use global disOnt namespace
    predicate = URIRef(namespace+predicateName) # GenerateProperty URI
    if predicateName in propertyTypes:	# use specified datatype for the property if defined
      predicateType = propertyTypes[predicateName] # Property type

    # OBJECT (value)
    object = Literal(data[i]) 
    #print subject, predicate, data[i]
    #print subject, predicate, object, predicateType

    # Fix date, and if possible, convert numbers to decimals (also integers!)
    if fields[i]=="DateYMD":
      object = fixDate(ind, data[i])

    # This is currently done in the else part of the conditional
#	elif fields[i]=="Event": 
      # if len(data[i])>0:
        # object = Literal(data[i]) 
      # else:
        # object = None

    # This elif is done below
#    elif fields[i] in ['Seccion','Magnitude','DataCards','Deaths','Injured','Missing','HousesDestroyed','HousesDamaged','Victims','Affected','Relocated','Evacuated','LossesUSD','LossesLocal','EducationCenters','Hospitals','DamagesincropsHa','Durationd','fichaslatitude','fichaslongitude']: 
#      print "FOUND", fields[i], data[i]
#      try:
#        object = Literal(float(data[i]),datatype=XSD.decimal) 
#      except ValueError:
#        object = None 
    elif fields[i] in fieldNames[countryCode]:
      type = propertyTypes[predicateName]	# Extract data type for the property
      if type==XSD.string:	# STRING
        if len(data[i])>0:
          object = Literal(data[i],datatype=XSD.string) 
        else:
          object = None
      elif type==XSD.nonNegativeInteger:	# INTEGER (and its variations)
        try:
          object = Literal(int(data[i]),datatype=XSD.nonNegativeInteger)
        except ValueError:
          object = None
#	  elif type==XSD.double:
#		try:
#	      object = Literal(float(data[i]),datatype=XSD.double)
#		except ValueError:
#		  object = None
	  # elif type==GEO.Latitude:
		# try:
	      # object = Literal(float(data[i]),datatype=GEO.Latitude)
		# except ValueError:
		  # object = None
	  # elif type==GEO.Longitude:
		# try:
	      # object = Literal(float(data[i]),datatype=GEO.Longitude)
		# except ValueError:
		  # object = None
	  # elif type==XSD.float:
		# try:
	      # object = Literal(float(data[i]),datatype=XSD.float)
		# except ValueError:
		  # object = None
	  # elif type==XSD.decimal:
		# try:
	      # object = Literal(float(data[i]),datatype=XSD.decimal)
		# except ValueError:
		  # object = None
      elif type==XSD.double or type==XSD.float or type==XSD.decimal or type==geoNs.Latitude or type==geoNs.Longitude:	# FLOAT (and its variations)
        try:
          object = Literal(float(data[i]),datatype=type)
    	except ValueError:
    	  object = None
      else:
        if len(data[i])>0:
          object = Literal(data[i]) 
        else:
          object = None
    else: 
      if len(data[i])>0: # If data is not empty
        object = Literal(data[i]) # assert object
      else:
        object = None 
    # Note that we assert the statement only if the object value is not None
    if object: g.add( (subject, predicate, object) ) # Assert the statement (only if the object value is not None)
    # See if correct statements were asserted...
    #print "STMNT", data[i], object

  # Add Country Information (name and code)
  g.add( (subject, URIRef(hasCountryName), Literal(countryName, datatype=XSD.string)) ) # Add Country Name Property
  g.add( (subject, URIRef(hasCountryCode), Literal(countryCode, datatype=XSD.string)) ) # Add Country Code Property
  
  # Add info about dataset origin (alternatively, could use graph name...)
  g.add( (subject, URIRef(hasOrigin), URIRef(nsSource)) )
  g.add( (subject, URIRef(fromFile), Literal(filename)) )
  
  #add type and class of rdf record
  g.add( (subject, RDF.type, URIRef(DisasterRecordType)) )
  g.add( (subject, RDF.type, OWL.NamedIndividual) )
  
  
  
######################################################################################
# Execution starts from here...  
######################################################################################

#Check input parameters. Should be 2:
# Parameter 1: csv file 
# Parameter 2: Country Code ISO Alpha 2 (ISO3166-1)
if len(sys.argv)<3:
  print "Simple disaster csv to rdf adapter."
  print "Synopsis: python adapter.py source.csv CountryCode"
  print "  * source.csv: .CSV text file. Fields on first line. One disaster record per line. field separator §"
  print "  * CountryCode: 2 Char code of the country based on the ISO3166-1 alpha-2 standard."
  print " Example: python adapter.py DI123413-Spain.csv SP"
  print "(Premature exit because one or more input arguments is missing.)"
  sys.exit(0)

# Print START
print "RDF Adapter started (file: "+sys.argv[1]+", country code: "+sys.argv[2]+")..."


# GLOBAL PARAMETERS
######################

# COUNTRIES: Dictionary relating country codes (ISO 3166-1) and country names (ISO 3166/MA)
# 	-- TODO: Complete list of countries, now only some have been added (those existing in Desinventar)
countries = {"UY":"Uruguay", "CR":"Costa Rica", "GT":"Guatemala", "ES":"Spain", "FI":"Finland", "MX":"Mexico", "PA":"Panama", "PE":"Peru", "VE":"Venezuela", "AL":"Albania", "RS":"Serbia", "NI":"Nicaragua", "NL":"Netherlands", "NP":"Nepal", "JM":"Jamaica", "HN":"Honduras", "GY":"Guyana", "SV":"El Salvador", "EC":"Ecuador", "CO":"Colombia", "CL":"Chile", "BO":"Bolivia", "ID":"Indonesia"}

# INPUT PARAMETERS
# Extract file and country from input parameters
inputfilename = sys.argv[1]	#Extract Filename of input file
countryCode = sys.argv[2] #Extract Country Code ISO3166-1 alpha2
countryName = countries[countryCode] #Extract Country Name ISO3166-1/MA

# Print Country
print "Processind data for country "
print "  * Country Name: "+countryName
print "  * Country ISO3166-1 alpha2 Code: "+countryCode

filename = (inputfilename.split(".csv"))[0] # crop suffix from filename

# NAMESPACES
# disOnt (global) 
nsGlobalprefix = "do" # Global ns prefix for disaster ontology namespace
nsGlobal = "http://www.tut.fi/mat/disasterOnt/" # Global disaster ontology namespace URI
globalNs = Namespace(nsGlobal) # Create DO_SOURCE namespace

# disOnt (local/source) 
nsSourceprefix = "do_"+countryCode # GENERALIZED Ns prefix for local/source disont
nsSource = nsGlobal+countryCode+"/"  # GENERALIZED Namespace URI for local/source disont
sourceNs = Namespace(nsSource) # Create DO namespace

# CREATE NAMESPACES NOT EXISTING IN rdflib
geoNsprefix = "geo"
nsGeo = "http://www.w3.org/2003/01/geo/wgs84_pos#"
geoNs = Namespace(nsGeo) # Create GEO namespace

# DisasterEvent Class
DisasterRecordType = nsGlobal+"DisasterEvent" # Global DisasterEvent Class

# Country-Specific properties / predicates
#(TODO: change so that these are automatically induced from the filename, for automatic processing...)
hasCountryName = nsGlobal+"CountryName" # Global hasCountryName predicate
hasCountryCode = nsGlobal+"CountryISOalpha2" # Global hasCountryCode predicate
hasOrigin = nsGlobal+"hasOrigin" # Global hasOrigin predicate
fromFile = nsGlobal+"fromFile" # Global fromFile predicate

# DATA PROPERTIES/FIELDS
# PROPERTY DATATYPES - Dictionary containing the correspondence between the Data types and the properties in the main ontology
propertyTypes = {"disasterCode":XSD.string,"TypeOfDisaster":globalNs.Disaster,"CountryISOalpha2":XSD.string,"CountryName":XSD.string,"ADL1Code":XSD.string,"ADL1Name":XSD.string,"ADL2Code":XSD.string,"ADL2Name":XSD.string,"ADL3Code":XSD.string,"ADL3Name":XSD.string,"Location":XSD.string,"StartDate":XSD.dateTime,"Comments":XSD.string,"disasterName":XSD.string,"Cause":XSD.string,"DescriptionOfCause":XSD.string,"SourceName":XSD.string,"ScaleValue":XSD.string,"MagnitudeScale":XSD.string,"GLIDE":XSD.string,"NumberOfDeaths":XSD.nonNegativeInteger,"NumberOfInjured":XSD.nonNegativeInteger,"NumberOfMissing":XSD.nonNegativeInteger,"HousesDestroyed":XSD.nonNegativeInteger,"HousesAffected":XSD.nonNegativeInteger,"TotalAffected":XSD.nonNegativeInteger,"NumberOfAffected":XSD.nonNegativeInteger,"NumberOfRelocated":XSD.nonNegativeInteger,"NumberOfEvacuated":XSD.nonNegativeInteger,"TotalEstimatedDamagesUSD":XSD.nonNegativeInteger,"TotalEstimatedDamagesLocal":XSD.nonNegativeInteger,"EducationCenters":XSD.nonNegativeInteger,"Hospitals":XSD.nonNegativeInteger,"Crops":XSD.double,"LostCattle":XSD.nonNegativeInteger,"Roads":XSD.double,"SectorsAffected":XSD.string,"Duration":XSD.nonNegativeInteger,"Latitude":geoNs.Latitude,"Longitude":geoNs.Longitude,"RiverBasin":XSD.string}

# FIELDS CORRESPONDENCES: Dictionary of Dictionaries of the Correspondences between the property names in local ontology and the property names in the main ontology. 
fieldNames = {} # Empty dictionary. It will contain a dictionary for each country.
#Albania
fieldNames["AL"] = {"Serial":"disasterCode","CodeRegion":"ADL1Code","Region":"ADL1Name","CodeDistrict":"ADL2Code","District":"ADL2Name","CodeCommune":"ADL3Code","Commune":"ADL3Name","Location":"Location","DateYMD":"StartDate","Comments":"Comments","Cause":"Cause","DescriptionofCause":"DescriptionOfCause","Source":"SourceName","Magnitude":"ScaleValue","GLIDEnumber":"GLIDE","OtherSectors":"SectorsAffected","Deaths":"NumberOfDeaths","Injured":"NumberOfInjured","Missing":"NumberOfMissing","HousesDestroyed":"HousesDestroyed","HousesDamaged":"HousesAffected","Victims":"TotalAffected","Affected":"NumberOfAffected","Relocated":"NumberOfRelocated","Evacuated":"NumberOfEvacuated","LossesUSD":"TotalEstimatedDamagesUSD","LossesLocal":"TotalEstimatedDamagesLocal","EducationCenters":"EducationCenters","Hospitals":"Hospitals","DamagesincropsHa":"Crops","Durationd":"Duration","fichaslatitude":"Latitude","fichaslongitude":"Longitude"}
#Bolivia
fieldNames["BO"] = {"Serial":"disasterCode","CodeDepartamento":"ADL1Code","Departamento":"ADL1Name","CodeProvincia":"ADL2Code","Provincia":"ADL2Name","CodeMunicipio":"ADL3Code","Municipio":"ADL3Name","Location":"Location","DateYMD":"StartDate","Comments":"Comments","Cause":"Cause","DescriptionofCause":"DescriptionOfCause","Source":"SourceName","Magnitude":"ScaleValue","GLIDEnumber":"GLIDE","OtherSectors":"SectorsAffected","Deaths":"NumberOfDeaths","Injured":"NumberOfInjured","Missing":"NumberOfMissing","HousesDestroyed":"HousesDestroyed","HousesDamaged":"HousesAffected","Victims":"TotalAffected","Affected":"NumberOfAffected","Relocated":"NumberOfRelocated","Evacuated":"NumberOfEvacuated","LossesUSD":"TotalEstimatedDamagesUSD","LossesLocal":"TotalEstimatedDamagesLocal","EducationCenters":"EducationCenters","Hospitals":"Hospitals","DamagesincropsHa":"Crops","DamagesinroadsMts":"Roads","Durationd":"Duration","fichaslatitude":"Latitude","fichaslongitude":"Longitude"}
#Chile
fieldNames["CL"] = {"Serial":"disasterCode","CodeRegion":"ADL1Code","Region":"ADL1Name","CodeProvincia":"ADL2Code","Provincia":"ADL2Name","CodeComuna":"ADL3Code","Comuna":"ADL3Name","Location":"Location","DateYMD":"StartDate","Comments":"Comments","Cause":"Cause","DescriptionofCause":"DescriptionOfCause","Source":"SourceName","Magnitude":"ScaleValue","GLIDEnumber":"GLIDE","OtherSectors":"SectorsAffected","Deaths":"NumberOfDeaths","Injured":"NumberOfInjured","Missing":"NumberOfMissing","HousesDestroyed":"HousesDestroyed","HousesDamaged":"HousesAffected","Victims":"TotalAffected","Affected":"NumberOfAffected","Relocated":"NumberOfRelocated","Evacuated":"NumberOfEvacuated","LossesUSD":"TotalEstimatedDamagesUSD","LossesLocal":"TotalEstimatedDamagesLocal","EducationCenters":"EducationCenters","Hospitals":"Hospitals","DamagesincropsHa":"Crops","DamagesinroadsMts":"Roads","Durationd":"Duration","fichaslatitude":"Latitude","fichaslongitude":"Longitude"}
#Colombia
fieldNames["CO"] = {"Serial":"disasterCode","CodeDepartamento":"ADL1Code","Departamento":"ADL1Name","CodeMunicipio":"ADL2Code","Municipio":"ADL2Name","DateYMD":"StartDate","Comments":"Comments","Cause":"Cause","DescriptionofCause":"DescriptionOfCause","Source":"SourceName","Magnitude":"ScaleValue","GLIDEnumber":"GLIDE","OtherSectors":"SectorsAffected","Deaths":"NumberOfDeaths","Injured":"NumberOfInjured","Missing":"NumberOfMissing","HousesDestroyed":"HousesDestroyed","HousesDamaged":"HousesAffected","Victims":"TotalAffected","Affected":"NumberOfAffected","Relocated":"NumberOfRelocated","Evacuated":"NumberOfEvacuated","LossesUSD":"TotalEstimatedDamagesUSD","LossesLocal":"TotalEstimatedDamagesLocal","EducationCenters":"EducationCenters","Hospitals":"Hospitals","DamagesincropsHa":"Crops","LostCattle":"LostCattle","DamagesinroadsMts":"Roads","Durationd":"Duration","fichaslatitude":"Latitude","fichaslongitude":"Longitude"}
#Costa Rica
fieldNames["CR"] = {"Serial":"disasterCode","CodeProvincia":"ADL1Code","Provincia":"ADL1Name","CodeCanton":"ADL2Code","Canton":"ADL2Name","CodeDistrito":"ADL3Code","Distrito":"ADL3Name","Location":"Location","DateYMD":"StartDate","Comments":"Comments","Cause":"Cause","DescriptionofCause":"DescriptionOfCause","Source":"SourceName","Magnitude":"ScaleValue","GLIDEnumber":"GLIDE","OtherSectors":"SectorsAffected","Deaths":"NumberOfDeaths","Injured":"NumberOfInjured","Missing":"NumberOfMissing","HousesDestroyed":"HousesDestroyed","HousesDamaged":"HousesAffected","Victims":"TotalAffected","Affected":"NumberOfAffected","Relocated":"NumberOfRelocated","Evacuated":"NumberOfEvacuated","LossesUSD":"TotalEstimatedDamagesUSD","LossesLocal":"TotalEstimatedDamagesLocal","EducationCenters":"EducationCenters","Hospitals":"Hospitals","DamagesincropsHa":"Crops","DamagesinroadsMts":"Roads","Durationd":"Duration","fichaslatitude":"Latitude","fichaslongitude":"Longitude"}
#Guatemala
fieldNames["GT"] = {"Serial":"disasterCode","CodeDepartamento":"ADL1Code","Departamento":"ADL1Name","CodeMunicipio":"ADL2Code","Municipio":"ADL2Name","CodeZona":"ADL3Code","Zona":"ADL3Name","Location":"Location","DateYMD":"StartDate","Comments":"Comments","Cause":"Cause","DescriptionofCause":"DescriptionOfCause","Source":"SourceName","Magnitude":"ScaleValue","GLIDEnumber":"GLIDE","OtherSectors":"SectorsAffected","Deaths":"NumberOfDeaths","Injured":"NumberOfInjured","Missing":"NumberOfMissing","HousesDestroyed":"HousesDestroyed","HousesDamaged":"HousesAffected","Victims":"TotalAffected","Affected":"NumberOfAffected","Relocated":"NumberOfRelocated","Evacuated":"NumberOfEvacuated","LossesUSD":"TotalEstimatedDamagesUSD","LossesLocal":"TotalEstimatedDamagesLocal","EducationCenters":"EducationCenters","Hospitals":"Hospitals","DamagesincropsHa":"Crops","DamagesinroadsMts":"Roads","Durationd":"Duration","fichaslatitude":"Latitude","fichaslongitude":"Longitude"}
#Uruguay
fieldNames["UY"] = {"Serial":"disasterCode","CodeDepartamento":"ADL1Code","Departamento":"ADL1Name","CodeSeccion":"ADL2Code","Seccion":"ADL2Name","Location":"Location","DateYMD":"StartDate","Comments":"Comments","Cause":"Cause","DescriptionofCause":"DescriptionOfCause","Source":"SourceName","Magnitude":"ScaleValue","GLIDEnumber":"GLIDE","OtherSectors":"SectorsAffected","Deaths":"NumberOfDeaths","Injured":"NumberOfInjured","Missing":"NumberOfMissing","HousesDestroyed":"HousesDestroyed","HousesDamaged":"HousesAffected","Victims":"TotalAffected","Affected":"NumberOfAffected","Relocated":"NumberOfRelocated","Evacuated":"NumberOfEvacuated","LossesUSD":"TotalEstimatedDamagesUSD","LossesLocal":"TotalEstimatedDamagesLocal","EducationCenters":"EducationCenters","Hospitals":"Hospitals","DamagesincropsHa":"Crops","Durationd":"Duration","fichaslatitude":"Latitude","fichaslongitude":"Longitude"} # UY IGNORED: "Event":"","CodeTerritorionacional":"CountryISOalpha2","TerritorioNacional":"CountryName","DataCards":"DONOTINCLUDE",

# IGNORED FIELDS: Dictionary containing the names of the properties, in fields[i], that are ignored and thus not added to the model
ignoredFields = ["CodeTerritorionacional", "Territorionacional", "DataCards", "Relief", "Formula"]


#############################
# START CREATING ONTOLOGY
#############################

# Create Empty Model
g = rdflib.Graph(); # Empty model to start with

# Add (Bind) Namespaces (Set nice-looking ns prefixes)
g.bind('owl', URIRef("http://www.w3.org/2002/07/owl#")) # OWL Namespace Prefix
g.bind(nsGlobalprefix, globalNs) # Global Namespace Prefix
g.bind(nsSourceprefix, sourceNs) # Source/local Namespace Prefix
g.bind('geo', geoNs) # GEO Namespace Prefix (for latitude and longitude)

# Add ontology name 
#g.add( (URIRef(nsSource+"_"+str(startTime)), RDF.type, OWL.Ontology) )
g.add( (URIRef(nsSource), RDF.type, OWL.Ontology) )

# Read the csv source
f = codecs.open(inputfilename, 'r', 'utf-8') # Open csv file in read-only mode

iik=0 	#True record counter
firstline = True 	#Check if first line (column headers)
fields = []	#list of properties (column headers)
prevLine = ""

for ind,line in enumerate(f): # for each line in input csv file...
#ind: contains the line number
#line: contains the actual line

  line = line.strip()  # Remove spaces from beginning and end of line

  #Concatenate line with next line in the case of unexpected newline char
  if not firstline and line.count(u"§") != (len(fields) -1): # assume n of fields is ok...
    # NOTE: If input cell includes newline, csv will break into multiple lines -- now a
    # simple (dirty) fix heuristic; if the line does not include correct number or '§'s, concat with next line
    # --- in a sense "fixing" csv input... (perhaps this is a bug in OO calc?)
    print "Warning (4): Csv input in multiple lines, fixin (line counter %d  now one too big)." % ind
#    print line
    prevLine = prevLine + line
    continue
  else:
    line = prevLine + line
    prevLine = "" 

  #Check if first line to extract the fields (column headers)
  if firstline: # Read col headers and store them in the fields array
    firstline = False
    fields = line.split(u'§')  # Split fields separated by '§'
    fields = fixAsLocalNames(fields)  # Fix field names
	
	# Print Found Fields
    print "Found fields: ", fields
	
    describeFieldsAsOwlProperties(g,fields,fieldNames[countryCode]) # This should be removed or modified, as most the properties are described in the main ontology.
    continue

  data = line.split(u'§')  # Split line in fields, separated by '§'
  addToModel(g,fields,data,ind,filename) # Add record to model
  
#  if iik>1: break
  iik = iik + 1 # Increase true record count 

#print " --> iik = "+str(iik)
f.close() # Close input csv file

print "Processed "+str(ind)+" lines."
print "Wrote "+str(iik)+" records."

# Serialize model and write to file
f = codecs.open(filename+".xml", 'w', 'utf-8') # Open/create xml output file to store model
f.write(g.serialize(format="xml").decode('utf8')) # Write model to file
f.close() # Close output file

g.close() # Close model

sec = time.time() - startTime
print "Finished in %.2f seconds." % sec
sys.exit(0)

###########################################
#   END
###########################################