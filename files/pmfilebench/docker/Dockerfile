ARG ERIC_ENM_RHEL6BASE_IMAGE_NAME=eric-enm-rhel6base
ARG ERIC_ENM_RHEL6BASE_IMAGE_REPO=armdocker.rnd.ericsson.se/proj-enm
ARG ERIC_ENM_RHEL6BASE_IMAGE_TAG=1.0.432-0

FROM openjdk:8
ARG _IMAGE_CONTENT_=config
ARG _JARS_=$_IMAGE_CONTENT_/*.jar
ARG _LTE_RESOURCES_=$_IMAGE_CONTENT_/60k_LTE.xml
ARG _TEST_LTE_RESOURCES_=$_IMAGE_CONTENT_/test_LTE.xml
ARG _WRAN_RESOURCES_=$_IMAGE_CONTENT_/50k_WRAN.xml
ARG _ARTIFACTS_HOME_=/pmfilebench/

RUN mkdir -p $_ARTIFACTS_HOME_
COPY ${_JARS_} $_ARTIFACTS_HOME_
COPY $_LTE_RESOURCES_ $_ARTIFACTS_HOME_
COPY $_TEST_LTE_RESOURCES_ $_ARTIFACTS_HOME_
COPY $_WRAN_RESOURCES_ $_ARTIFACTS_HOME_
#ENTRYPOINT ["java","-cp", "/pmfilebench/iotest.jar", "-DlowThreads=400", "-DhighThreads=109", "-Diotest.length=15", "-DprocessNodeB=true", "writer.IoWriter", "/loaddir/", "/pmfilebench/test_LTE.xml"]

#ENTRYPOINT ["java", "-cp", "/pmfilebench/iotest.jar", "-Dreadsize=32", "-Dthreads=16", "-DfileTypes=GPEH,XML,CTR,UETR", "-DprocessNodeB=true", "reader.IoReader", "/loaddir/", "/pmfilebench/test_LTE.xml"]
